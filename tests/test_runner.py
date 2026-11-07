from pathlib import Path
import sys
import tempfile
import unittest

from evalforge.core import EvalForgeError
from evalforge.runner import run_suite

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "examples" / "tasks.jsonl"
MOCK = ROOT / "examples" / "mock_model.py"


class RunnerTests(unittest.TestCase):
    def test_demo_suite_passes_offline(self):
        payload = run_suite(TASKS, f"{sys.executable} {MOCK}")
        self.assertEqual(payload["summary"]["count"], 6)
        self.assertEqual(payload["summary"]["passed"], 6)
        self.assertEqual(payload["summary"]["errors"], 0)
        self.assertEqual(payload["summary"]["mean_score"], 1.0)

    def test_results_keep_task_order_with_workers(self):
        payload = run_suite(TASKS, f"{sys.executable} {MOCK}", workers=3)
        self.assertEqual(
            [item["task_id"] for item in payload["results"]],
            ["extract-city-json", "incident-summary", "calculation", "evaluation-summary", "classification", "general-principles"],
        )

    def test_tag_filter(self):
        payload = run_suite(TASKS, f"{sys.executable} {MOCK}", only_tags=["classification"])
        self.assertEqual(payload["summary"]["count"], 1)
        self.assertEqual(payload["results"][0]["task_id"], "classification")

    def test_nonzero_adapter_exit_becomes_error(self):
        payload = run_suite(TASKS, f"{sys.executable} -c 'import sys; sys.exit(7)'", only_tags=["classification"])
        result = payload["results"][0]
        self.assertFalse(result["passed"])
        self.assertEqual(result["score"], 0.0)
        self.assertIn("exited 7", result["error"])

    def test_missing_adapter_becomes_error(self):
        payload = run_suite(TASKS, "/definitely/missing/adapter", only_tags=["classification"])
        self.assertIn("failed to start", payload["results"][0]["error"])

    def test_retry_attempts_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            counter = Path(tmp) / "count"
            script = Path(tmp) / "flaky.py"
            script.write_text(
                "import pathlib, sys\n"
                f"p=pathlib.Path({str(counter)!r})\n"
                "n=int(p.read_text()) if p.exists() else 0\n"
                "p.write_text(str(n+1))\n"
                "sys.exit(1 if n == 0 else 0)\n",
                encoding="utf-8",
            )
            payload = run_suite(TASKS, f"{sys.executable} {script}", retries=1, only_tags=["classification"])
        self.assertEqual(payload["results"][0]["attempts"], 2)
        self.assertIsNone(payload["results"][0]["error"])

    def test_invalid_timeout_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "Timeout must be positive"):
            run_suite(TASKS, f"{sys.executable} {MOCK}", timeout=0)

    def test_invalid_workers_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "Workers must be at least 1"):
            run_suite(TASKS, f"{sys.executable} {MOCK}", workers=0)

    def test_invalid_retries_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "Retries must be non-negative"):
            run_suite(TASKS, f"{sys.executable} {MOCK}", retries=-1)

    def test_empty_command_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "must not be empty"):
            run_suite(TASKS, " ", only_tags=["classification"])


if __name__ == "__main__":
    unittest.main()
