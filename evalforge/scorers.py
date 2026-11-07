"""Deterministic, inspectable scorers for model and agent output."""

from __future__ import annotations

from collections import Counter
import json
import math
import re
from typing import Any

from .core import EvalForgeError, ScoreDetail, Task


_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _norm(text: Any, *, case_sensitive: bool = False) -> str:
    value = str(text).strip()
    value = re.sub(r"\s+", " ", value)
    return value if case_sensitive else value.lower()


def _score(passed: bool, type_name: str, detail: str, score: float | None = None) -> ScoreDetail:
    return ScoreDetail(type=type_name, passed=passed, score=(1.0 if passed else 0.0) if score is None else score, detail=detail)


def _json_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(key in actual and _json_subset(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) > len(actual):
            return False
        return all(_json_subset(value, actual[index]) for index, value in enumerate(expected))
    return expected == actual


def _tokens(text: str) -> Counter[str]:
    return Counter(re.findall(r"[\w']+", text.lower()))


def _token_f1(reference: str, candidate: str) -> float:
    expected = _tokens(reference)
    actual = _tokens(candidate)
    if not expected or not actual:
        return 1.0 if not expected and not actual else 0.0
    overlap = sum((expected & actual).values())
    if overlap == 0:
        return 0.0
    precision = overlap / sum(actual.values())
    recall = overlap / sum(expected.values())
    return 2 * precision * recall / (precision + recall)


def score_check(check: dict[str, Any], output: str, task: Task) -> ScoreDetail:
    """Score one check against an adapter's text output."""

    check_type = check.get("type")
    if not isinstance(check_type, str) or not check_type:
        raise EvalForgeError(f"Task {task.id!r} has a check without a type")
    check_type = check_type.strip().lower()

    if check_type == "exact":
        expected = check.get("value", task.expected)
        if expected is None:
            raise EvalForgeError(f"Task {task.id!r} exact check needs value")
        case_sensitive = bool(check.get("case_sensitive", False))
        passed = _norm(output, case_sensitive=case_sensitive) == _norm(expected, case_sensitive=case_sensitive)
        return _score(passed, "exact", f"expected {str(expected)!r}")

    if check_type == "contains":
        case_sensitive = bool(check.get("case_sensitive", False))
        haystack = output if case_sensitive else output.lower()
        if "all_of" in check:
            values = check["all_of"]
            if not isinstance(values, list) or not values or any(not isinstance(item, str) for item in values):
                raise EvalForgeError(f"Task {task.id!r} contains all_of needs strings")
            needles = values
            missing = [item for item in needles if (item if case_sensitive else item.lower()) not in haystack]
            return _score(not missing, "contains", "all terms present" if not missing else f"missing {missing!r}")
        if "any_of" in check:
            values = check["any_of"]
            if not isinstance(values, list) or not values or any(not isinstance(item, str) for item in values):
                raise EvalForgeError(f"Task {task.id!r} contains any_of needs strings")
            found = [item for item in values if (item if case_sensitive else item.lower()) in haystack]
            return _score(bool(found), "contains", f"matched {found[0]!r}" if found else "no allowed term found")
        value = check.get("value", task.expected)
        if not isinstance(value, str) or not value:
            raise EvalForgeError(f"Task {task.id!r} contains check needs a non-empty value")
        needle = value if case_sensitive else value.lower()
        return _score(needle in haystack, "contains", f"expected substring {value!r}")

    if check_type == "regex":
        pattern = check.get("pattern", check.get("value"))
        if not isinstance(pattern, str) or not pattern:
            raise EvalForgeError(f"Task {task.id!r} regex check needs a pattern")
        flags = 0 if bool(check.get("case_sensitive", True)) else re.IGNORECASE
        try:
            passed = re.search(pattern, output, flags=flags) is not None
        except re.error as exc:
            raise EvalForgeError(f"Task {task.id!r} has invalid regex {pattern!r}: {exc}") from exc
        return _score(passed, "regex", f"pattern {pattern!r}")

    if check_type == "json":
        expected = check.get("value", task.expected)
        if isinstance(expected, str):
            try:
                expected = json.loads(expected)
            except json.JSONDecodeError as exc:
                raise EvalForgeError(f"Task {task.id!r} JSON check has invalid expected JSON") from exc
        try:
            actual = json.loads(output)
        except json.JSONDecodeError:
            return _score(False, "json", "output is not valid JSON")
        subset = bool(check.get("subset", False))
        passed = _json_subset(expected, actual) if subset else expected == actual
        return _score(passed, "json", "subset match" if subset else "exact JSON match")

    if check_type == "similarity":
        reference = check.get("value", task.expected)
        if not isinstance(reference, str) or not reference.strip():
            raise EvalForgeError(f"Task {task.id!r} similarity check needs a reference value")
        threshold = float(check.get("threshold", 0.8))
        if not 0.0 <= threshold <= 1.0:
            raise EvalForgeError(f"Task {task.id!r} similarity threshold must be between 0 and 1")
        score = _token_f1(reference, output)
        return ScoreDetail("similarity", score >= threshold, score, f"token F1 {score:.3f}, threshold {threshold:.3f}")

    if check_type == "numeric":
        expected = check.get("value", task.expected)
        if isinstance(expected, bool) or not isinstance(expected, (int, float)) or not math.isfinite(float(expected)):
            raise EvalForgeError(f"Task {task.id!r} numeric check needs a finite number")
        match = _NUMBER_RE.search(output)
        if not match:
            return _score(False, "numeric", f"no number found; expected {expected}")
        actual = float(match.group(0))
        tolerance = float(check.get("tolerance", 0.0))
        relative = float(check.get("relative_tolerance", 0.0))
        if tolerance < 0 or relative < 0:
            raise EvalForgeError(f"Task {task.id!r} numeric tolerances must be non-negative")
        allowed = max(tolerance, abs(float(expected)) * relative)
        difference = abs(actual - float(expected))
        return _score(difference <= allowed, "numeric", f"got {actual:g}, expected {float(expected):g}, tolerance {allowed:g}")

    if check_type == "length":
        unit = str(check.get("unit", "words")).lower()
        if unit not in {"words", "chars"}:
            raise EvalForgeError(f"Task {task.id!r} length unit must be words or chars")
        actual = len(output.split()) if unit == "words" else len(output)
        minimum = check.get("min")
        maximum = check.get("max")
        if minimum is None and maximum is None:
            raise EvalForgeError(f"Task {task.id!r} length check needs min or max")
        if minimum is not None and actual < int(minimum):
            return _score(False, "length", f"{actual} {unit}, below min {minimum}")
        if maximum is not None and actual > int(maximum):
            return _score(False, "length", f"{actual} {unit}, above max {maximum}")
        return _score(True, "length", f"{actual} {unit}")

    raise EvalForgeError(f"Task {task.id!r} has unsupported check type {check_type!r}")


def score_task(task: Task, output: str) -> tuple[float, bool, tuple[ScoreDetail, ...]]:
    details = tuple(score_check(check, output, task) for check in task.checks)
    score = sum(detail.score for detail in details) / len(details)
    passed = all(detail.passed for detail in details)
    return score, passed, details
