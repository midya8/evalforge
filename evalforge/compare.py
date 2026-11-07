"""Compare two evaluation runs and surface regressions first."""

from __future__ import annotations

from typing import Any

from .core import EvalForgeError, TaskResult, load_run


def compare_runs(baseline_path: str, candidate_path: str, *, max_drop: float = 0.0) -> dict[str, Any]:
    if max_drop < 0:
        raise EvalForgeError("max_drop must be non-negative")
    baseline = load_run(baseline_path)
    candidate = load_run(candidate_path)
    base_results = {item["task_id"]: TaskResult.from_dict(item) for item in baseline["results"]}
    cand_results = {item["task_id"]: TaskResult.from_dict(item) for item in candidate["results"]}
    common = sorted(set(base_results) & set(cand_results))
    missing = sorted(set(base_results) - set(cand_results))
    added = sorted(set(cand_results) - set(base_results))
    regressions = []
    improvements = []
    unchanged = []
    for task_id in common:
        before = base_results[task_id]
        after = cand_results[task_id]
        delta = after.score - before.score
        item = {
            "task_id": task_id,
            "baseline_score": before.score,
            "candidate_score": after.score,
            "delta": delta,
            "baseline_passed": before.passed,
            "candidate_passed": after.passed,
            "candidate_error": after.error,
        }
        if delta < -max_drop or (before.passed and not after.passed):
            regressions.append(item)
        elif delta > 0 or (after.passed and not before.passed):
            improvements.append(item)
        else:
            unchanged.append(item)
    base_summary = baseline.get("summary", {})
    cand_summary = candidate.get("summary", {})
    return {
        "baseline": baseline_path,
        "candidate": candidate_path,
        "max_drop": max_drop,
        "summary": {
            "common": len(common),
            "missing_in_candidate": len(missing),
            "added_in_candidate": len(added),
            "regressions": len(regressions),
            "improvements": len(improvements),
            "unchanged": len(unchanged),
            "mean_score_delta": float(cand_summary.get("mean_score", 0.0)) - float(base_summary.get("mean_score", 0.0)),
            "pass_rate_delta": float(cand_summary.get("pass_rate", 0.0)) - float(base_summary.get("pass_rate", 0.0)),
        },
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "missing_in_candidate": missing,
        "added_in_candidate": added,
        "ok": not regressions and not missing,
    }
