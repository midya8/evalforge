"""Compare runs by id without confusing a changed cohort with paired change."""
from __future__ import annotations
import math
from typing import Any
from .core import EvalForgeError, TaskResult, load_run, summarize, finite_number


def compare_payloads(baseline: dict, candidate: dict, *, max_drop: float = 0.0,
                     baseline_name: str = "baseline", candidate_name: str = "candidate") -> dict[str, Any]:
    if not finite_number(max_drop) or max_drop < 0:
        raise EvalForgeError("max_drop must be finite and non-negative")
    # load_run validates file inputs; the public in-memory entry point validates too.
    from .core import validate_run
    baseline, candidate = validate_run(baseline), validate_run(candidate)
    base_results = {item["task_id"]: TaskResult.from_dict(item) for item in baseline["results"]}
    cand_results = {item["task_id"]: TaskResult.from_dict(item) for item in candidate["results"]}
    common = sorted(set(base_results) & set(cand_results))
    missing = sorted(set(base_results) - set(cand_results))
    added = sorted(set(cand_results) - set(base_results))
    groups = {"regressions": [], "improvements": [], "unchanged": []}
    witnesses = []
    for task_id in common:
        before, after = base_results[task_id], cand_results[task_id]
        delta = after.score - before.score
        score_drop = delta < -max_drop
        pass_lost = before.passed and not after.passed
        group = "regressions" if score_drop or pass_lost else "improvements" if delta > 0 or (after.passed and not before.passed) else "unchanged"
        item = {"task_id": task_id, "baseline_score": before.score, "candidate_score": after.score,
                "delta": delta, "baseline_passed": before.passed, "candidate_passed": after.passed,
                "candidate_error": after.error}
        groups[group].append(item)
        witnesses.append({**item, "baseline": before.to_dict(), "candidate": after.to_dict(),
                          "score_drop": score_drop, "pass_lost": pass_lost, "classification": group,
                          "score_margin": delta + max_drop})
    bs, cs = summarize(list(base_results.values())).to_dict(), summarize(list(cand_results.values())).to_dict()
    pb, pc = summarize([base_results[k] for k in common]).to_dict(), summarize([cand_results[k] for k in common]).to_dict()
    return {"baseline": baseline_name, "candidate": candidate_name, "max_drop": max_drop,
            "summary": {"common": len(common), "missing_in_candidate": len(missing), "added_in_candidate": len(added),
                        **{g: len(v) for g, v in groups.items()},
                        "mean_score_delta": cs["mean_score"] - bs["mean_score"],
                        "pass_rate_delta": cs["pass_rate"] - bs["pass_rate"]},
            "paired_summary": {"count": len(common), "defined": bool(common), "baseline_mean": pb["mean_score"] if common else None,
                               "candidate_mean": pc["mean_score"] if common else None,
                               "mean_score_delta": pc["mean_score"] - pb["mean_score"] if common else None,
                               "pass_rate_delta": pc["pass_rate"] - pb["pass_rate"] if common else None},
            "recomputed_summaries": {"baseline": bs, "candidate": cs}, "witnesses": witnesses,
            **groups, "missing_in_candidate": missing, "added_in_candidate": added,
            "ok": not groups["regressions"] and not missing}


def compare_runs(baseline_path: str, candidate_path: str, *, max_drop: float = 0.0) -> dict[str, Any]:
    return compare_payloads(load_run(baseline_path), load_run(candidate_path), max_drop=max_drop,
                            baseline_name=baseline_path, candidate_name=candidate_path)
