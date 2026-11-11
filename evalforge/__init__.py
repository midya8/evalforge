"""EvalForge: local-first evaluation for LLM and agent outputs."""

from .core import EvalForgeError, RunSummary, ScoreDetail, Task, TaskResult, load_tasks, load_run, summarize, write_run
from .runner import run_suite
from .scorers import score_task

__all__ = [
    "EvalForgeError",
    "RunSummary",
    "ScoreDetail",
    "Task",
    "TaskResult",
    "load_tasks",
    "load_run",
    "run_suite",
    "score_task",
    "summarize",
    "write_run",
]

__version__ = "0.2.0"

from .family import family_report
__all__.append("family_report")
