"""Command line interface for EvalForge."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .compare import compare_runs
from .core import EvalForgeError, load_run, load_tasks, write_run
from .report import render_html, write_compare_markdown, write_html, write_junit, write_markdown
from .runner import run_suite


def _print_run_summary(payload: dict) -> None:
    summary = payload["summary"]
    print(
        f"{summary['passed']}/{summary['count']} passed · "
        f"mean score {summary['mean_score']:.3f} · "
        f"errors {summary['errors']} · p95 {summary['p95_latency_ms']:.0f} ms"
    )


def _print_compare(payload: dict) -> None:
    summary = payload["summary"]
    print(
        f"{summary['regressions']} regressions · {summary['improvements']} improvements · "
        f"{summary['unchanged']} unchanged · mean score delta {summary['mean_score_delta']:+.3f}"
    )
    for item in payload["regressions"][:10]:
        print(
            f"REGRESSION {item['task_id']}: {item['baseline_score']:.3f} -> "
            f"{item['candidate_score']:.3f} ({item['delta']:+.3f})"
        )
    if payload["missing_in_candidate"]:
        print("Missing in candidate: " + ", ".join(payload["missing_in_candidate"][:10]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evalforge",
        description="Local-first evaluation for LLM and agent outputs.",
    )
    parser.add_argument("--version", action="version", version=f"evalforge {__version__}")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    run = subparsers.add_parser("run", help="run a JSONL task suite through an adapter command")
    run.add_argument("--tasks", required=True, help="JSONL task file")
    run.add_argument("--cmd", required=True, help="adapter command; prompt arrives on stdin")
    run.add_argument("--out", required=True, help="write run JSON here")
    run.add_argument("--report", help="optional self-contained HTML report path")
    run.add_argument("--junit", help="optional JUnit XML report path")
    run.add_argument("--markdown", help="optional Markdown job summary path")
    run.add_argument("--timeout", type=float, default=30.0, help="per-task adapter timeout in seconds")
    run.add_argument("--retries", type=int, default=0, help="retry failed adapter calls this many times")
    run.add_argument("--workers", type=int, default=1, help="parallel adapter calls")
    run.add_argument("--tag", action="append", default=[], help="only run tasks with this tag; repeatable")
    run.add_argument("--fail-under", type=float, default=0.0, help="exit 1 when mean score is below this threshold")

    validate = subparsers.add_parser("validate", help="validate a JSONL task file without running adapters")
    validate.add_argument("tasks", help="JSONL task file")

    report = subparsers.add_parser("report", help="render a run JSON file as standalone HTML")
    report.add_argument("run", help="run JSON file")
    report.add_argument("--html", required=True, help="output HTML file")

    compare = subparsers.add_parser("compare", help="compare candidate results against a baseline run")
    compare.add_argument("baseline", help="baseline run JSON")
    compare.add_argument("candidate", help="candidate run JSON")
    compare.add_argument("--max-drop", type=float, default=0.0, help="allowed per-task score decrease")
    compare.add_argument("--format", choices=("text", "json"), default="text")
    compare.add_argument("--markdown", help="optional Markdown comparison summary path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command_name == "validate":
            tasks = load_tasks(args.tasks)
            print(f"validated {len(tasks)} tasks")
            return 0

        if args.command_name == "run":
            payload = run_suite(
                args.tasks,
                args.cmd,
                timeout=args.timeout,
                retries=args.retries,
                workers=args.workers,
                only_tags=args.tag or None,
            )
            write_run(args.out, payload)
            if args.report:
                write_html(args.out, args.report)
            if args.junit:
                write_junit(args.out, args.junit)
            if args.markdown:
                write_markdown(args.out, args.markdown)
            _print_run_summary(payload)
            if not 0.0 <= args.fail_under <= 1.0:
                raise EvalForgeError("--fail-under must be between 0 and 1")
            if payload["summary"]["mean_score"] < args.fail_under:
                print(f"mean score below gate {args.fail_under:.3f}", file=sys.stderr)
                return 1
            return 0

        if args.command_name == "report":
            write_html(args.run, args.html)
            print(f"wrote {args.html}")
            return 0

        if args.command_name == "compare":
            payload = compare_runs(args.baseline, args.candidate, max_drop=args.max_drop)
            if args.markdown:
                write_compare_markdown(payload, args.markdown)
            if args.format == "json":
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                _print_compare(payload)
            return 0 if payload["ok"] else 1
    except EvalForgeError as exc:
        print(f"evalforge: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
