"""Run task suites through any local or hosted model adapter command."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import Any

from .core import EvalForgeError, Task, TaskResult, load_tasks, summarize, finite_number
from .scorers import score_task


def _run_once(task: Task, command: str, timeout: float) -> tuple[str, str | None, float]:
    args = shlex.split(command)
    if not args:
        raise EvalForgeError("Adapter command must not be empty")
    env = os.environ.copy()
    env["EVALFORGE_TASK_ID"] = task.id
    env["EVALFORGE_PROMPT"] = task.prompt
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            input=task.prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            cwd=str(Path.cwd()),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "", f"adapter timed out after {timeout:g}s", timeout * 1000.0
    except OSError as exc:
        return "", f"adapter failed to start: {exc}", (time.perf_counter() - start) * 1000.0
    latency_ms = (time.perf_counter() - start) * 1000.0
    output = completed.stdout.rstrip("\n")
    if completed.returncode != 0:
        stderr = completed.stderr.strip().splitlines()
        detail = stderr[-1] if stderr else f"exit {completed.returncode}"
        return output, f"adapter exited {completed.returncode}: {detail}", latency_ms
    return output, None, latency_ms


def _run_task(task: Task, command: str, timeout: float, retries: int) -> TaskResult:
    attempts = 0
    output = ""
    error: str | None = None
    latency_ms = 0.0
    while attempts <= retries:
        attempts += 1
        output, error, latency_ms = _run_once(task, command, timeout)
        if error is None:
            break
    if error is None:
        score, passed, details = score_task(task, output)
    else:
        score, passed, details = 0.0, False, ()
    return TaskResult(
        task_id=task.id,
        output=output,
        score=score,
        passed=passed,
        checks=details,
        latency_ms=latency_ms,
        attempts=attempts,
        error=error,
        tags=task.tags,
    )


def run_suite(
    tasks_path: str | Path,
    command: str,
    *,
    timeout: float = 30.0,
    retries: int = 0,
    workers: int = 1,
    only_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Run a JSONL task suite and return a serializable run payload."""

    if not finite_number(timeout) or timeout <= 0:
        raise EvalForgeError("Timeout must be positive")
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
        raise EvalForgeError("Retries must be non-negative")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise EvalForgeError("Workers must be at least 1")
    tasks = load_tasks(tasks_path, only_tags=only_tags)
    if workers == 1 or len(tasks) == 1:
        results = [_run_task(task, command, timeout, retries) for task in tasks]
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
            results = list(pool.map(lambda task: _run_task(task, command, timeout, retries), tasks))
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tasks_path": str(tasks_path),
        "command": command,
        "summary": summarize(results).to_dict(),
        "results": [result.to_dict() for result in results],
    }
