import unittest

from evalforge.core import EvalForgeError, Task
from evalforge.scorers import score_task


def task(checks, expected=None):
    return Task.from_dict({"id": "t", "prompt": "p", "expected": expected, "checks": checks})


class ScorerTests(unittest.TestCase):
    def detail(self, check, output, expected=None):
        score, passed, details = score_task(task([check], expected), output)
        self.assertEqual(len(details), 1)
        return score, passed, details[0]

    def test_exact_normalizes_whitespace_and_case(self):
        _, passed, detail = self.detail({"type": "exact", "value": " Billing  Team "}, "billing team")
        self.assertTrue(passed)
        self.assertEqual(detail.score, 1.0)

    def test_exact_can_be_case_sensitive(self):
        _, passed, _ = self.detail({"type": "exact", "value": "Billing", "case_sensitive": True}, "billing")
        self.assertFalse(passed)

    def test_contains_all_of_reports_missing(self):
        _, passed, detail = self.detail({"type": "contains", "all_of": ["alpha", "beta"]}, "alpha only")
        self.assertFalse(passed)
        self.assertIn("beta", detail.detail)

    def test_contains_any_of(self):
        _, passed, detail = self.detail({"type": "contains", "any_of": ["red", "blue"]}, "blue answer")
        self.assertTrue(passed)
        self.assertIn("blue", detail.detail)

    def test_contains_requires_value(self):
        with self.assertRaisesRegex(EvalForgeError, "non-empty value"):
            self.detail({"type": "contains"}, "output", expected=None)

    def test_regex_matches_case_insensitive(self):
        _, passed, _ = self.detail({"type": "regex", "pattern": "p95 under \\d+ ms", "case_sensitive": False}, "P95 under 420 ms")
        self.assertTrue(passed)

    def test_invalid_regex_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "invalid regex"):
            self.detail({"type": "regex", "pattern": "["}, "output")

    def test_json_exact_match(self):
        _, passed, _ = self.detail({"type": "json", "value": {"ok": True, "n": 2}}, '{"n":2,"ok":true}')
        self.assertTrue(passed)

    def test_json_subset_match(self):
        _, passed, _ = self.detail({"type": "json", "value": {"user": {"id": 7}}, "subset": True}, '{"user":{"id":7,"name":"A"},"extra":1}')
        self.assertTrue(passed)

    def test_json_invalid_output_fails_not_crashes(self):
        _, passed, detail = self.detail({"type": "json", "value": {"ok": True}}, "not json")
        self.assertFalse(passed)
        self.assertIn("not valid JSON", detail.detail)

    def test_similarity_scores_token_overlap(self):
        score, passed, detail = self.detail(
            {"type": "similarity", "value": "versioned deterministic evaluation reports", "threshold": 0.5},
            "deterministic evaluation reports",
        )
        self.assertTrue(passed)
        self.assertGreater(score, 0.5)
        self.assertIn("token F1", detail.detail)

    def test_similarity_threshold_validation(self):
        with self.assertRaisesRegex(EvalForgeError, "between 0 and 1"):
            self.detail({"type": "similarity", "value": "x", "threshold": 1.1}, "x")

    def test_numeric_extracts_first_number(self):
        _, passed, detail = self.detail({"type": "numeric", "value": 42}, "The answer is 42.")
        self.assertTrue(passed)
        self.assertIn("42", detail.detail)

    def test_numeric_absolute_tolerance(self):
        _, passed, _ = self.detail({"type": "numeric", "value": 10, "tolerance": 0.5}, "10.4")
        self.assertTrue(passed)

    def test_numeric_relative_tolerance(self):
        _, passed, _ = self.detail({"type": "numeric", "value": 100, "relative_tolerance": 0.01}, "100.5")
        self.assertTrue(passed)

    def test_numeric_missing_number_fails(self):
        _, passed, detail = self.detail({"type": "numeric", "value": 10}, "no digits")
        self.assertFalse(passed)
        self.assertIn("no number", detail.detail)

    def test_length_words_bounds(self):
        _, passed, _ = self.detail({"type": "length", "unit": "words", "min": 2, "max": 4}, "three word answer")
        self.assertTrue(passed)

    def test_length_chars_bounds(self):
        _, passed, _ = self.detail({"type": "length", "unit": "chars", "max": 4}, "abcde")
        self.assertFalse(passed)

    def test_length_needs_bound(self):
        with self.assertRaisesRegex(EvalForgeError, "needs min or max"):
            self.detail({"type": "length"}, "x")

    def test_unknown_check_type_rejected(self):
        with self.assertRaisesRegex(EvalForgeError, "unsupported check type"):
            self.detail({"type": "vibes"}, "x")

    def test_score_task_averages_multiple_checks(self):
        score, passed, details = score_task(
            task([
                {"type": "contains", "value": "alpha"},
                {"type": "contains", "value": "beta"},
            ]),
            "alpha only",
        )
        self.assertEqual(score, 0.5)
        self.assertFalse(passed)
        self.assertEqual(len(details), 2)


if __name__ == "__main__":
    unittest.main()
