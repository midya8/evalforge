import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from evalforge import __version__
from evalforge.cli import main
from evalforge.compare import compare_runs
from evalforge.report import render_compare_markdown, render_html, render_markdown
from evalforge.runner import run_suite
from evalforge.core import write_run

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "examples" / "tasks.jsonl"
MOCK = ROOT / "examples" / "mock_model.py"


class CliTests(unittest.TestCase):
    def test_validate_command(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["validate", str(TASKS)])
        self.assertEqual(code, 0)
        self.assertIn("validated 6 tasks", out.getvalue())

    def test_run_command_writes_json_and_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "run.json"
            html_path = Path(tmp) / "report.html"
            junit_path = Path(tmp) / "junit.xml"
            markdown_path = Path(tmp) / "summary.md"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([
                    "run", "--tasks", str(TASKS), "--cmd", f"{sys.executable} {MOCK}",
                    "--out", str(run_path), "--report", str(html_path), "--junit", str(junit_path), "--markdown", str(markdown_path), "--fail-under", "1.0",
                ])
            self.assertEqual(code, 0)
            self.assertTrue(run_path.is_file())
            html = html_path.read_text(encoding="utf-8")
            junit = ET.parse(junit_path).getroot()
            markdown = markdown_path.read_text(encoding="utf-8")
        self.assertIn("EvalForge report", html)
        self.assertIn("extract-city-json", html)
        self.assertEqual(junit.tag, "testsuite")
        self.assertEqual(junit.attrib["tests"], "6")
        self.assertEqual(junit.attrib["failures"], "0")
        self.assertEqual(len(junit.findall("testcase")), 6)
        self.assertIn("# EvalForge evaluation", markdown)
        self.assertIn("**Status:** PASS", markdown)
        self.assertIn("| Tasks | 6 |", markdown)
        self.assertIn("| extract-city-json | PASS |", markdown)
        self.assertIn("6/6 passed", out.getvalue())

    def test_run_command_gate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "run.json"
            code = main([
                "run", "--tasks", str(TASKS), "--cmd", f"{sys.executable} -c 'print(1)'",
                "--out", str(run_path), "--tag", "classification", "--fail-under", "1.0",
            ])
        self.assertEqual(code, 1)

    def test_report_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "run.json"
            html_path = Path(tmp) / "report.html"
            write_run(run_path, run_suite(TASKS, f"{sys.executable} {MOCK}", only_tags=["classification"]))
            code = main(["report", str(run_path), "--html", str(html_path)])
            self.assertEqual(code, 0)
            self.assertIn("classification", html_path.read_text(encoding="utf-8"))

    def test_invalid_command_input_returns_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["validate", "/missing/tasks.jsonl"])
        self.assertEqual(code, 2)
        self.assertIn("Task file not found", err.getvalue())


class CompareTests(unittest.TestCase):
    def make_run(self, path, score, passed=True):
        payload = {
            "schema_version": 1,
            "created_at": "now",
            "tasks_path": "tasks.jsonl",
            "command": "cmd",
            "summary": {"count": 1, "passed": int(passed), "failed": int(not passed), "errors": 0, "pass_rate": float(passed), "mean_score": score, "median_latency_ms": 1, "p95_latency_ms": 1, "tags": []},
            "results": [{"task_id": "a", "output": "x", "score": score, "passed": passed, "checks": [], "latency_ms": 1, "attempts": 1, "error": None, "tags": []}],
        }
        write_run(path, payload)

    def test_compare_detects_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            cand = Path(tmp) / "cand.json"
            self.make_run(base, 1.0, True)
            self.make_run(cand, 0.5, False)
            payload = compare_runs(str(base), str(cand))
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["summary"]["regressions"], 1)
        self.assertEqual(payload["regressions"][0]["task_id"], "a")

    def test_compare_max_drop_allows_small_decline_when_still_passing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            cand = Path(tmp) / "cand.json"
            self.make_run(base, 1.0, True)
            self.make_run(cand, 0.96, True)
            payload = compare_runs(str(base), str(cand), max_drop=0.05)
        self.assertTrue(payload["ok"])

    def test_compare_missing_candidate_task_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            cand = Path(tmp) / "cand.json"
            self.make_run(base, 1.0, True)
            write_run(cand, {"schema_version": 1, "created_at": "now", "tasks_path": "t", "command": "c", "summary": {}, "results": []})
            payload = compare_runs(str(base), str(cand))
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["missing_in_candidate"], ["a"])

    def test_compare_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            cand = Path(tmp) / "cand.json"
            self.make_run(base, 1.0, True)
            self.make_run(cand, 1.0, True)
            markdown_path = Path(tmp) / "comparison.md"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["compare", str(base), str(cand), "--format", "json", "--markdown", str(markdown_path)])
            payload = json.loads(out.getvalue())
            markdown = markdown_path.read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertIn("# EvalForge regression comparison", markdown)
        self.assertIn("**Status:** PASS", markdown)
        self.assertIn("| Common tasks | 1 |", markdown)
        self.assertIn("| Regressions | 0 |", markdown)


class ReportTests(unittest.TestCase):
    def test_compare_markdown_escapes_paths_and_tasks(self):
        payload = {
            "baseline": "base|run.json",
            "candidate": "candidate\nrun.json",
            "max_drop": 0.05,
            "summary": {"common": 1, "missing_in_candidate": 0, "added_in_candidate": 0, "regressions": 1, "improvements": 0, "unchanged": 0, "mean_score_delta": -0.5, "pass_rate_delta": -1.0},
            "regressions": [{"task_id": "task|one", "baseline_score": 1.0, "candidate_score": 0.5, "delta": -0.5, "baseline_passed": True, "candidate_passed": False, "candidate_error": None}],
            "improvements": [],
            "missing_in_candidate": [],
            "added_in_candidate": [],
            "ok": False,
        }
        markdown = render_compare_markdown(payload)
        self.assertIn("base\|run.json", markdown)
        self.assertIn("candidate run.json", markdown)
        self.assertIn("task\|one", markdown)
        self.assertIn("**Status:** FAIL", markdown)

    def test_html_escapes_model_output(self):
        payload = run_suite(TASKS, f"{sys.executable} -c 'print(\"<script>alert(1)</script>\")'", only_tags=["classification"])
        html = render_html(payload)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_markdown_escapes_table_cells(self):
        payload = run_suite(TASKS, f"{sys.executable} {MOCK}")
        payload["command"] = "mock|model"
        payload["results"][0]["task_id"] = "task|one"
        markdown = render_markdown(payload)
        self.assertIn("mock\\|model", markdown)
        self.assertIn("task\\|one", markdown)

    def test_html_contains_tag_rollup(self):
        html = render_html(run_suite(TASKS, f"{sys.executable} {MOCK}"))
        self.assertIn("classification", html)
        self.assertIn("Score by tag", html)


class SarifTests(unittest.TestCase):
    def test_run_sarif_clean_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "run.json"
            sarif_path = Path(tmp) / "analysis.sarif"
            code = main([
                "run", "--tasks", str(TASKS), "--cmd", f"{sys.executable} {MOCK}",
                "--out", str(run_path), "--sarif", str(sarif_path), "--fail-under", "1.0",
            ])
            doc = json.loads(sarif_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(doc["$schema"], "https://json.schemastore.org/sarif-2.1.0.json")
        run = doc["runs"][0]
        driver = run["tool"]["driver"]
        self.assertEqual(driver["name"], "EvalForge")
        self.assertEqual(driver["version"], __version__)
        self.assertEqual(driver["informationUri"], "https://github.com/midya8/evalforge")
        self.assertEqual(run["results"], [])
        self.assertEqual(driver["rules"], [])
        self.assertTrue(run["invocations"][0]["executionSuccessful"])

    def test_run_sarif_marks_failed_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "run.json"
            sarif_path = Path(tmp) / "analysis.sarif"
            code = main([
                "run", "--tasks", str(TASKS), "--cmd", f"{sys.executable} -c 'print(1)'",
                "--out", str(run_path), "--sarif", str(sarif_path),
            ])
            doc = json.loads(sarif_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        run = doc["runs"][0]
        results = run["results"]
        self.assertEqual(len(results), 6)
        self.assertTrue(all(item["level"] == "error" for item in results))
        self.assertEqual({item["ruleId"] for item in results}, {"EVALFORGE_TASK_FAILED"})
        task_ids = {item["properties"]["task_id"] for item in results}
        self.assertIn("extract-city-json", task_ids)
        for item in results:
            location = item["locations"][0]["physicalLocation"]
            self.assertEqual(location["artifactLocation"]["uri"], str(run_path).replace("\\", "/"))
            self.assertEqual(location["region"]["startLine"], 1)
        rule_ids = {rule["id"] for rule in run["tool"]["driver"]["rules"]}
        self.assertEqual(rule_ids, {"EVALFORGE_TASK_FAILED"})
        self.assertFalse(run["invocations"][0]["executionSuccessful"])

    def test_run_sarif_marks_adapter_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "run.json"
            sarif_path = Path(tmp) / "analysis.sarif"
            code = main([
                "run", "--tasks", str(TASKS), "--cmd", f"{sys.executable} -c 'import sys; sys.exit(3)'",
                "--out", str(run_path), "--sarif", str(sarif_path),
            ])
            doc = json.loads(sarif_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        run = doc["runs"][0]
        self.assertEqual({item["ruleId"] for item in run["results"]}, {"EVALFORGE_ADAPTER_ERROR"})
        self.assertTrue(all("adapter error" in item["message"]["text"] for item in run["results"]))
        self.assertFalse(run["invocations"][0]["executionSuccessful"])

    def test_compare_sarif_marks_regressions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            cand = Path(tmp) / "cand.json"
            sarif_path = Path(tmp) / "comparison.sarif"
            CompareTests().make_run(base, 1.0, True)
            CompareTests().make_run(cand, 0.5, False)
            code = main(["compare", str(base), str(cand), "--sarif", str(sarif_path)])
            doc = json.loads(sarif_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        run = doc["runs"][0]
        self.assertEqual(len(run["results"]), 1)
        item = run["results"][0]
        self.assertEqual(item["ruleId"], "EVALFORGE_REGRESSION")
        self.assertEqual(item["level"], "error")
        self.assertIn("1.000 -> 0.500", item["message"]["text"])
        self.assertEqual(item["properties"]["task_id"], "a")
        self.assertEqual(item["properties"]["delta"], -0.5)
        uri = item["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        self.assertEqual(uri, str(cand).replace("\\", "/"))
        self.assertFalse(run["invocations"][0]["executionSuccessful"])

    def test_compare_sarif_marks_missing_tasks_as_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            cand = Path(tmp) / "cand.json"
            sarif_path = Path(tmp) / "comparison.sarif"
            CompareTests().make_run(base, 1.0, True)
            write_run(cand, {"schema_version": 1, "created_at": "now", "tasks_path": "t", "command": "c", "summary": {}, "results": []})
            code = main(["compare", str(base), str(cand), "--sarif", str(sarif_path)])
            doc = json.loads(sarif_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        run = doc["runs"][0]
        self.assertEqual(len(run["results"]), 1)
        item = run["results"][0]
        self.assertEqual(item["ruleId"], "EVALFORGE_MISSING_TASK")
        self.assertEqual(item["level"], "warning")
        self.assertEqual(item["properties"]["task_id"], "a")

    def test_compare_sarif_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            cand = Path(tmp) / "cand.json"
            sarif_path = Path(tmp) / "comparison.sarif"
            CompareTests().make_run(base, 1.0, True)
            CompareTests().make_run(cand, 1.0, True)
            code = main(["compare", str(base), str(cand), "--sarif", str(sarif_path)])
            doc = json.loads(sarif_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        run = doc["runs"][0]
        self.assertEqual(run["results"], [])
        self.assertTrue(run["invocations"][0]["executionSuccessful"])
        driver = run["tool"]["driver"]
        self.assertEqual(driver["name"], "EvalForge")
        self.assertEqual(driver["version"], __version__)


if __name__ == "__main__":
    unittest.main()
