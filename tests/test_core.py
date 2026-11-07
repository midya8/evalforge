import json
from pathlib import Path
import tempfile
import unittest

from evalforge.core import EvalForgeError, Task, load_run, load_tasks, summarize, write_run


class TaskModelTests(unittest.TestCase):
    def test_string_expected_defaults_to_exact_check(self):
        task = Task.from_dict({"id": "a", "prompt": "p", "expected": "yes"})
        self.assertEqual(task.checks, ({"type": "exact", "value": "yes"},))

    def test_json_expected_defaults_to_json_check(self):
        task = Task.from_dict({"id": "a", "prompt": "p", "expected": {"ok": True}})
        self.assertEqual(task.checks, ({"type": "json", "value": {"ok": True}},))

    def test_numeric_expected_defaults_to_numeric_check(self):
        task = Task.from_dict({"id": "a", "prompt": "p", "expected": 3.5})
        self.assertEqual(task.checks, ({"type": "numeric", "value": 3.5},))

    def test_blank_id_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "non-empty string id"):
            Task.from_dict({"id": " ", "prompt": "p", "expected": "x"})

    def test_blank_prompt_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "non-empty string prompt"):
            Task.from_dict({"id": "a", "prompt": " ", "expected": "x"})

    def test_checks_must_be_objects(self):
        with self.assertRaisesRegex(EvalForgeError, "checks must be a list of objects"):
            Task.from_dict({"id": "a", "prompt": "p", "checks": ["exact"]})

    def test_missing_acceptance_criteria_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "needs checks or expected"):
            Task.from_dict({"id": "a", "prompt": "p"})

    def test_tags_must_be_non_empty_strings(self):
        with self.assertRaisesRegex(EvalForgeError, "tags must be non-empty strings"):
            Task.from_dict({"id": "a", "prompt": "p", "expected": "x", "tags": [""]})

    def test_metadata_must_be_object(self):
        with self.assertRaisesRegex(EvalForgeError, "metadata must be an object"):
            Task.from_dict({"id": "a", "prompt": "p", "expected": "x", "metadata": []})


class LoadTasksTests(unittest.TestCase):
    def write(self, directory, text):
        path = Path(directory) / "tasks.jsonl"
        path.write_text(text, encoding="utf-8")
        return path

    def test_loads_jsonl_and_ignores_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, '{"id":"a","prompt":"p","expected":"x"}\n\n{"id":"b","prompt":"q","expected":"y"}\n')
            tasks = load_tasks(path)
        self.assertEqual([task.id for task in tasks], ["a", "b"])

    def test_duplicate_id_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, '{"id":"a","prompt":"p","expected":"x"}\n{"id":"a","prompt":"q","expected":"y"}\n')
            with self.assertRaisesRegex(EvalForgeError, "Duplicate task id"):
                load_tasks(path)

    def test_invalid_json_reports_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, '{"id":"a"\n')
            with self.assertRaisesRegex(EvalForgeError, "Invalid JSON on line 1"):
                load_tasks(path)

    def test_missing_file_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "Task file not found"):
            load_tasks("/definitely/missing/tasks.jsonl")

    def test_tag_filter_selects_matching_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(
                tmp,
                '{"id":"a","prompt":"p","expected":"x","tags":["one"]}\n'
                '{"id":"b","prompt":"q","expected":"y","tags":["two"]}\n',
            )
            tasks = load_tasks(path, only_tags=["two"])
        self.assertEqual([task.id for task in tasks], ["b"])

    def test_empty_selection_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, '{"id":"a","prompt":"p","expected":"x","tags":["one"]}\n')
            with self.assertRaisesRegex(EvalForgeError, "No tasks selected"):
                load_tasks(path, only_tags=["other"])


class RunRecordTests(unittest.TestCase):
    def test_summary_counts_and_tags(self):
        from evalforge.core import ScoreDetail, TaskResult

        results = [
            TaskResult("a", "x", 1.0, True, (ScoreDetail("exact", True, 1.0, "ok"),), 10, tags=("one",)),
            TaskResult("b", "y", 0.0, False, (ScoreDetail("exact", False, 0.0, "bad"),), 30, error="exit", tags=("one", "two")),
        ]
        summary = summarize(results)
        self.assertEqual(summary.count, 2)
        self.assertEqual(summary.passed, 1)
        self.assertEqual(summary.errors, 1)
        self.assertEqual(summary.pass_rate, 0.5)
        self.assertEqual(summary.median_latency_ms, 10)
        self.assertEqual(summary.p95_latency_ms, 30)
        self.assertEqual(summary.tags[0].tag, "one")
        self.assertEqual(summary.tags[0].mean_score, 0.5)

    def test_write_and_load_run_round_trip(self):
        payload = {
            "schema_version": 1,
            "created_at": "now",
            "tasks_path": "tasks.jsonl",
            "command": "cmd",
            "summary": {"count": 1, "passed": 1, "failed": 0, "errors": 0, "pass_rate": 1.0, "mean_score": 1.0, "median_latency_ms": 1, "p95_latency_ms": 1, "tags": []},
            "results": [{"task_id": "a", "output": "x", "score": 1.0, "passed": True, "checks": [{"type": "exact", "passed": True, "score": 1.0, "detail": "ok"}], "latency_ms": 1, "attempts": 1, "error": None, "tags": []}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            write_run(path, payload)
            loaded = load_run(path)
        self.assertEqual(loaded["results"][0]["task_id"], "a")
        self.assertEqual(loaded["summary"]["passed"], 1)

    def test_load_run_rejects_invalid_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(EvalForgeError, "results list"):
                load_run(path)


if __name__ == "__main__":
    unittest.main()
