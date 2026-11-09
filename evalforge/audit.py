"""Bounded paired comparison witnesses and exhaustive integer sign flips.

No inference result changes the original per-task regression gate. Supplied
scores are not rescored outputs and equal ids do not prove equal task definitions.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from .compare import compare_payloads
from .core import EvalForgeError, validate_run


def _tick(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1 or not math.isfinite(v):
        raise EvalForgeError("Audit scores/max_drop must be finite in [0,1]")
    t = round(v * 1000)
    if abs(v * 1000 - t) > 1e-10:
        raise EvalForgeError("Audit scores/max_drop need a .001 grid")
    return t


def _text(s, size):
    if not isinstance(s, str) or len(s) > size or any(ord(c) > 126 or (ord(c) < 32 and c not in '\t\n\r') for c in s):
        raise EvalForgeError("Audit text must be bounded printable ASCII")


def audit_compare(spec):
    if not isinstance(spec, dict) or set(spec) - {"baseline", "candidate", "max_drop"} or not {"baseline", "candidate"} <= set(spec):
        raise EvalForgeError("Audit requires baseline/candidate lists and optional max_drop")
    norm = {"max_drop": _tick(spec.get("max_drop", 0)) / 1000}
    for side in ("baseline", "candidate"):
        rows = spec[side]
        if not isinstance(rows, list) or len(rows) > 12:
            raise EvalForgeError("Audit accepts at most 12 rows per run")
        for raw in rows:
            if not isinstance(raw, dict) or set(raw) - {"task_id", "score", "passed", "output", "error", "latency_ms", "attempts", "tags", "checks"}:
                raise EvalForgeError("Unknown audit result field")
            if isinstance(raw.get("checks", []), list) and any(not isinstance(c, dict) or set(c) - {"type", "passed", "score", "detail"} for c in raw.get("checks", [])):
                raise EvalForgeError("Unknown audit check field")
        run = validate_run({"results": rows})
        norm[side] = []
        for row in run["results"]:
            if set(row) - {"task_id", "score", "passed", "output", "error", "latency_ms", "attempts", "tags", "checks"}:
                raise EvalForgeError("Unknown audit result field")
            _text(row["task_id"], 64)
            _text(row["output"], 2048)
            if row["error"] is not None:
                _text(row["error"], 256)
            if len(row["tags"]) > 8 or len(row["checks"]) > 8 or row["latency_ms"] > 1000000 or row["attempts"] > 100:
                raise EvalForgeError("Audit row exceeds bounds")
            for tag in row["tags"]:
                _text(tag, 64)
            row["score"] = _tick(row["score"]) / 1000
            for c in row["checks"]:
                if set(c) - {"type", "passed", "score", "detail"}:
                    raise EvalForgeError("Unknown audit check field")
                _text(c["type"], 32)
                _text(c["detail"], 256)
                c["score"] = _tick(c["score"]) / 1000
            norm[side].append(row)
    result = compare_payloads({"results": norm["baseline"]}, {"results": norm["candidate"]}, max_drop=norm["max_drop"])
    if len(result["witnesses"]) > 8:
        raise EvalForgeError("Audit accepts at most eight matched pairs")
    pairs = []
    cells = {"both_pass": [], "lost_pass": [], "gained_pass": [], "both_fail": []}
    for row in result["witnesses"]:
        t = _tick(row["candidate_score"]) - _tick(row["baseline_score"])
        pairs.append({"task_id": row["task_id"], "delta_ticks": t})
        cell = "both_pass" if row["baseline_passed"] and row["candidate_passed"] else "lost_pass" if row["baseline_passed"] else "gained_pass" if row["candidate_passed"] else "both_fail"
        cells[cell].append(row["task_id"])
    active = [r for r in pairs if r["delta_ticks"] != 0]
    observed = sum(r["delta_ticks"] for r in pairs)
    assignments = []
    if pairs:
        for mask in range(1 << len(active)):
            signs = [-1 if mask & (1 << j) else 1 for j in range(len(active))]
            contributions = [s * r["delta_ticks"] for s, r in zip(signs, active)]
            total = sum(contributions)
            assignments.append({"mask": mask, "signs": signs, "contributions": contributions,
                                "sum_ticks": total, "extreme": abs(total) >= abs(observed)})
    extreme = sum(r["extreme"] for r in assignments)
    n = len(cells["lost_pass"]) + len(cells["gained_pass"])
    cut = min(len(cells["lost_pass"]), len(cells["gained_pass"]))
    binary = [{"gains": k, "ways": math.comb(n, k), "lower_tail": k <= cut} for k in range(n + 1)] if pairs else []
    lower = sum(r["ways"] for r in binary if r["lower_tail"])
    return {"schema_version": 1, "spec": norm, "comparison": result,
            "pair_differences": pairs, "pass_cells": cells,
            "sign_flip": {"defined": bool(pairs), "active_ids": [r["task_id"] for r in active],
                          "zero_ids": [r["task_id"] for r in pairs if not r["delta_ticks"]],
                          "observed_sum_ticks": observed, "assignments": assignments,
                          "extreme_count": extreme, "total": len(assignments),
                          "p_two_sided": extreme / len(assignments) if assignments else None},
            "mcnemar": {"defined": bool(pairs), "discordant": n, "lower_cutoff": cut,
                        "rows": binary, "lower_ways": lower, "total": 2 ** n if pairs else 0,
                        "p_two_sided": min(1.0, 2 * lower / (2 ** n)) if pairs else None}}


def load_spec(path):
    if Path(path).stat().st_size > 131072:
        raise EvalForgeError("Audit spec exceeds 128 KiB")
    def unique(items):
        d = {}
        for k, v in items:
            if k in d:
                raise EvalForgeError("Duplicate JSON key")
            d[k] = v
        return d
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(EvalForgeError("Nonfinite JSON")))
    except (ValueError, UnicodeError) as exc:
        raise EvalForgeError("Invalid audit JSON") from exc
