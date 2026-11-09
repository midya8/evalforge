"""Core data model and JSONL task loading."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable


def finite_number(value):
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except (OverflowError, TypeError):
        return False


class EvalForgeError(Exception):
    """Raised for invalid tasks, runs, or command-line inputs."""


@dataclass(frozen=True)
class Task:
    """One evaluation prompt and its executable checks."""

    id: str
    prompt: str
    expected: Any = None
    checks: tuple[dict[str, Any], ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, line: int | None = None) -> "Task":
        where = f" on line {line}" if line is not None else ""
        if not isinstance(data, dict):
            raise EvalForgeError(f"Task{where} must be a JSON object")
        task_id = data.get("id")
        prompt = data.get("prompt")
        if not isinstance(task_id, str) or not task_id.strip():
            raise EvalForgeError(f"Task{where} needs a non-empty string id")
        if not isinstance(prompt, str) or not prompt.strip():
            raise EvalForgeError(f"Task {task_id!r}{where} needs a non-empty string prompt")
        raw_checks = data.get("checks", [])
        if not isinstance(raw_checks, list) or any(not isinstance(item, dict) for item in raw_checks):
            raise EvalForgeError(f"Task {task_id!r}{where} checks must be a list of objects")
        checks = tuple(dict(item) for item in raw_checks)
        expected = data.get("expected")
        if not checks and expected is not None:
            if isinstance(expected, (dict, list)):
                checks = ({"type": "json", "value": expected},)
            elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
                checks = ({"type": "numeric", "value": expected},)
            elif isinstance(expected, str):
                checks = ({"type": "exact", "value": expected},)
        if not checks:
            raise EvalForgeError(f"Task {task_id!r}{where} needs checks or expected output")
        tags = data.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise EvalForgeError(f"Task {task_id!r}{where} tags must be non-empty strings")
        if len(set(tag.strip() for tag in tags)) != len(tags):
            raise EvalForgeError(f"Task {task_id!r}{where} tags must be unique")
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise EvalForgeError(f"Task {task_id!r}{where} metadata must be an object")
        return cls(
            id=task_id.strip(),
            prompt=prompt,
            expected=expected,
            checks=checks,
            tags=tuple(tag.strip() for tag in tags),
            metadata=dict(metadata),
        )


@dataclass(frozen=True)
class ScoreDetail:
    """The result of one executable check."""

    type: str
    passed: bool
    score: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "passed": self.passed, "score": self.score, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoreDetail":
        return cls(
            type=str(data.get("type", "unknown")),
            passed=bool(data.get("passed")),
            score=float(data.get("score", 0.0)),
            detail=str(data.get("detail", "")),
        )


@dataclass(frozen=True)
class TaskResult:
    """One adapter response and its check results."""

    task_id: str
    output: str
    score: float
    passed: bool
    checks: tuple[ScoreDetail, ...]
    latency_ms: float
    attempts: int = 1
    error: str | None = None
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "output": self.output,
            "score": self.score,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
            "latency_ms": self.latency_ms,
            "attempts": self.attempts,
            "error": self.error,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskResult":
        checks = tuple(ScoreDetail.from_dict(item) for item in data.get("checks", []))
        return cls(
            task_id=str(data.get("task_id", "")),
            output=str(data.get("output", "")),
            score=float(data.get("score", 0.0)),
            passed=bool(data.get("passed")),
            checks=checks,
            latency_ms=float(data.get("latency_ms", 0.0)),
            attempts=int(data.get("attempts", 1)),
            error=data.get("error") if data.get("error") is None else str(data.get("error")),
            tags=tuple(str(tag) for tag in data.get("tags", [])),
        )


@dataclass(frozen=True)
class TagSummary:
    tag: str
    count: int
    passed: int
    mean_score: float

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "count": self.count, "passed": self.passed, "mean_score": self.mean_score}


@dataclass(frozen=True)
class RunSummary:
    count: int
    passed: int
    failed: int
    errors: int
    pass_rate: float
    mean_score: float
    median_latency_ms: float
    p95_latency_ms: float
    tags: tuple[TagSummary, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "pass_rate": self.pass_rate,
            "mean_score": self.mean_score,
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "tags": [tag.to_dict() for tag in self.tags],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunSummary":
        return cls(
            count=int(data.get("count", 0)),
            passed=int(data.get("passed", 0)),
            failed=int(data.get("failed", 0)),
            errors=int(data.get("errors", 0)),
            pass_rate=float(data.get("pass_rate", 0.0)),
            mean_score=float(data.get("mean_score", 0.0)),
            median_latency_ms=float(data.get("median_latency_ms", 0.0)),
            p95_latency_ms=float(data.get("p95_latency_ms", 0.0)),
            tags=tuple(
                TagSummary(str(item["tag"]), int(item["count"]), int(item["passed"]), float(item["mean_score"]))
                for item in data.get("tags", [])
            ),
        )


def load_tasks(path: str | Path, *, only_tags: Iterable[str] | None = None) -> list[Task]:
    """Load a JSONL task file, rejecting duplicate ids and malformed rows."""

    task_path = Path(path)
    if not task_path.is_file():
        raise EvalForgeError(f"Task file not found: {task_path}")
    wanted = set(only_tags or ())
    tasks: list[Task] = []
    seen: set[str] = set()
    try:
        lines = task_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise EvalForgeError(f"Task file is not valid UTF-8: {task_path}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvalForgeError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
        task = Task.from_dict(raw, line=line_number)
        if task.id in seen:
            raise EvalForgeError(f"Duplicate task id {task.id!r} on line {line_number}")
        seen.add(task.id)
        if wanted and wanted.isdisjoint(task.tags):
            continue
        tasks.append(task)
    if not tasks:
        raise EvalForgeError("No tasks selected")
    return tasks


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return ordered[rank]


def _score_sum(items):
    """Ordered binary64 accumulation, stable across Python sum changes."""
    total = 0.0
    for item in items:
        total += item.score
    return total


def summarize(results: list[TaskResult]) -> RunSummary:
    count = len(results)
    passed = sum(1 for result in results if result.passed)
    errors = sum(1 for result in results if result.error)
    latencies = [result.latency_ms for result in results]
    by_tag: dict[str, list[TaskResult]] = {}
    for result in results:
        for tag in result.tags:
            by_tag.setdefault(tag, []).append(result)
    tags = tuple(
        TagSummary(
            tag=tag,
            count=len(items),
            passed=sum(1 for item in items if item.passed),
            mean_score=_score_sum(items) / len(items),
        )
        for tag, items in sorted(by_tag.items())
    )
    return RunSummary(
        count=count,
        passed=passed,
        failed=count - passed,
        errors=errors,
        pass_rate=(passed / count) if count else 0.0,
        mean_score=(_score_sum(results) / count) if count else 0.0,
        median_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
        tags=tags,
    )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def write_run(path: str | Path, payload: dict[str, Any]) -> None:
    _write_json_atomic(Path(path), payload)


def load_run(path: str | Path) -> dict[str, Any]:
    run_path = Path(path)
    if not run_path.is_file():
        raise EvalForgeError(f"Run file not found: {run_path}")
    try:
        payload = json.loads(run_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EvalForgeError(f"Invalid run JSON {run_path}: {exc}") from exc
    return validate_run(payload)


def validate_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate comparison/report evidence instead of coercing strings to booleans.

    Stored summaries are ignored and recomputed from validated rows. Optional
    legacy result fields retain defaults; id, score and passed are required.
    Unknown run/result metadata is preserved; this is not an authenticity check.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise EvalForgeError("Run must contain an object with a results list")
    def number(v, label, low=0, high=None):
        try:
            valid = not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and v >= low and (high is None or v <= high)
        except (OverflowError, TypeError):
            valid = False
        if not valid:
            raise EvalForgeError(label + " must be a finite number in range")
    seen, normalized = set(), []
    for row in payload["results"]:
        if not isinstance(row, dict) or not isinstance(row.get("task_id"), str) or not row["task_id"].strip():
            raise EvalForgeError("Result needs a non-empty task_id")
        key = row["task_id"]
        if key in seen:
            raise EvalForgeError("Duplicate result task_id: " + key)
        seen.add(key)
        number(row.get("score"), "Result score", high=1)
        if not isinstance(row.get("passed"), bool):
            raise EvalForgeError("Result passed must be Boolean")
        if not isinstance(row.get("output", ""), str) or (row.get("error") is not None and not isinstance(row["error"], str)):
            raise EvalForgeError("Result output/error must be text")
        number(row.get("latency_ms", 0), "Latency")
        attempts = row.get("attempts", 1)
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
            raise EvalForgeError("Attempts must be a positive integer")
        tags, checks = row.get("tags", []), row.get("checks", [])
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() for t in tags) or len(set(tags)) != len(tags):
            raise EvalForgeError("Result tags must be unique non-empty strings")
        if not isinstance(checks, list):
            raise EvalForgeError("Result checks must be a list")
        for c in checks:
            if not isinstance(c, dict) or not isinstance(c.get("type"), str) or not isinstance(c.get("passed"), bool) or not isinstance(c.get("detail", ""), str):
                raise EvalForgeError("Invalid check detail")
            number(c.get("score"), "Check score", high=1)
        # A result may legitimately pass with a partial score; do not infer pass from score.
        normalized.append({**row, **TaskResult.from_dict(row).to_dict()})
    results = [TaskResult.from_dict(r) for r in normalized]
    return {**payload, "results": normalized, "summary": summarize(results).to_dict()}
