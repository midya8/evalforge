import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from evalforge.cli import main
from evalforge.compare import compare_runs
from evalforge.report import render_html
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
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([
                    "run", "--tasks", str(TASKS), "--cmd", f"{sys.executable} {MOCK}",
                    "--out", str(run_path), "--report", str(html_path), "--fail-under", "1.0",
                ])
            self.assertEqual(code, 0)
            self.assertTrue(run_path.is_file())
            html = html_path.read_text(encoding="utf-8")
        self.assertIn("EvalForge report", html)
        self.assertIn("extract-city-json", html)
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
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["compare", str(base), str(cand), "--format", "json"])
            payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])


class ReportTests(unittest.TestCase):
    def test_html_escapes_model_output(self):
        payload = run_suite(TASKS, f"{sys.executable} -c 'print(\"<script>alert(1)</script>\")'", only_tags=["classification"])
        html = render_html(payload)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_html_contains_tag_rollup(self):
        html = render_html(run_suite(TASKS, f"{sys.executable} {MOCK}"))
        self.assertIn("classification", html)
        self.assertIn("Score by tag", html)


if __name__ == "__main__":
    unittest.main()
