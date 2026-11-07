"""Self-contained HTML reports for evaluation runs."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from . import __version__
from .core import load_run


_CSS = """
:root { color-scheme: light; --ink:#17202a; --muted:#5b6572; --line:#d9e0e7; --bg:#f6f8fa; --card:#fff; --good:#067647; --bad:#b42318; --accent:#2557d6; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }
main { max-width: 1180px; margin: 0 auto; padding: 40px 24px 64px; }
header { margin-bottom: 28px; }
h1 { margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.4rem); letter-spacing: -0.04em; }
.meta { color: var(--muted); margin: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 24px 0; }
.card, section { background: var(--card); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 8px 24px rgba(15,23,42,.05); }
.card { padding: 18px; }
.card strong { display: block; font-size: 1.7rem; margin-bottom: 4px; }
.card span { color: var(--muted); font-size: .9rem; }
section { margin-top: 18px; overflow: hidden; }
h2 { font-size: 1.05rem; margin: 0; padding: 16px 18px; border-bottom: 1px solid var(--line); }
table { width: 100%; border-collapse: collapse; font-size: .92rem; }
th, td { padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 650; background: #fbfcfd; }
tr:last-child td { border-bottom: 0; }
.badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 9px; font-size: .78rem; font-weight: 700; }
.pass { color: var(--good); background: #dcfae6; }
.fail { color: var(--bad); background: #fee4e2; }
.score { font-variant-numeric: tabular-nums; }
details { max-width: 520px; }
summary { cursor: pointer; color: var(--accent); }
pre { white-space: pre-wrap; overflow-wrap: anywhere; margin: 8px 0 0; padding: 10px; background: #f2f4f7; border-radius: 8px; }
footer { color: var(--muted); margin-top: 24px; font-size: .85rem; }
@media (max-width: 720px) { main { padding: 24px 12px; } table, thead, tbody, tr, th, td { display: block; } thead { display: none; } td { border: 0; padding: 8px 14px; } tr { border-bottom: 1px solid var(--line); padding: 8px 0; } }
"""


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_html(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    results = payload.get("results", [])
    cards = [
        ("Pass rate", _fmt_pct(float(summary.get("pass_rate", 0.0))), f"{summary.get('passed', 0)} of {summary.get('count', 0)} passed"),
        ("Mean score", f"{float(summary.get('mean_score', 0.0)):.3f}", "average check score"),
        ("Errors", str(summary.get("errors", 0)), "adapter failures"),
        ("p95 latency", f"{float(summary.get('p95_latency_ms', 0.0)):.0f} ms", "per task"),
    ]
    tag_rows = []
    for tag in summary.get("tags", []):
        tag_rows.append(
            "<tr>"
            f"<td>{escape(str(tag['tag']))}</td>"
            f"<td>{int(tag['passed'])} / {int(tag['count'])}</td>"
            f"<td class='score'>{float(tag['mean_score']):.3f}</td>"
            "</tr>"
        )
    result_rows = []
    for result in results:
        passed = bool(result.get("passed"))
        checks = result.get("checks", [])
        check_text = "; ".join(
            f"{item.get('type')}: {item.get('detail')}" for item in checks
        ) or str(result.get("error") or "no checks recorded")
        output = str(result.get("output", ""))
        if len(output) > 500:
            output = output[:500] + "…"
        result_rows.append(
            "<tr>"
            f"<td><strong>{escape(str(result.get('task_id', '')))}</strong></td>"
            f"<td><span class='badge {'pass' if passed else 'fail'}'>{'PASS' if passed else 'FAIL'}</span></td>"
            f"<td class='score'>{float(result.get('score', 0.0)):.3f}</td>"
            f"<td class='score'>{float(result.get('latency_ms', 0.0)):.0f} ms</td>"
            f"<td>{escape(check_text)}</td>"
            f"<td><details><summary>Output</summary><pre>{escape(output)}</pre></details></td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EvalForge report</title>
<style>{_CSS}</style>
</head>
<body>
<main>
<header>
<h1>EvalForge report</h1>
<p class="meta">Generated {escape(str(payload.get('created_at', 'unknown time')))} · Adapter <code>{escape(str(payload.get('command', '')))}</code></p>
</header>
<div class="grid">
{''.join(f"<div class='card'><strong>{escape(value)}</strong><span>{escape(label)} · {escape(note)}</span></div>" for value, label, note in cards)}
</div>
<section>
<h2>Score by tag</h2>
<table><thead><tr><th>Tag</th><th>Passed</th><th>Mean score</th></tr></thead><tbody>{''.join(tag_rows) or '<tr><td colspan="3">No tags</td></tr>'}</tbody></table>
</section>
<section>
<h2>Task results</h2>
<table><thead><tr><th>Task</th><th>Status</th><th>Score</th><th>Latency</th><th>Checks</th><th>Output</th></tr></thead><tbody>{''.join(result_rows)}</tbody></table>
</section>
<footer>Self-contained report generated by EvalForge. All model output is escaped before rendering.</footer>
</main>
</body>
</html>
"""


def write_html(run_path: str, html_path: str) -> None:
    payload = load_run(run_path)
    path = Path(html_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(payload), encoding="utf-8", newline="\n")


def _md_cell(value: Any, limit: int | None = None) -> str:
    text = str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    if limit is not None and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def render_markdown(payload: dict[str, Any]) -> str:
    """Render a concise Markdown summary suitable for CI job summaries."""
    summary = payload.get("summary", {})
    results = payload.get("results", [])
    passed = int(summary.get("passed", 0))
    count = int(summary.get("count", len(results)))
    errors = int(summary.get("errors", 0))
    status = "PASS" if count and passed == count and errors == 0 else "FAIL"
    lines = [
        "# EvalForge evaluation",
        "",
        f"**Status:** {status}",
        "",
        f"**Adapter:** `{_md_cell(payload.get('command', ''), 160)}`",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Tasks | {count} |",
        f"| Passed | {passed} |",
        f"| Failed | {int(summary.get('failed', max(0, count - passed)))} |",
        f"| Errors | {errors} |",
        f"| Pass rate | {_fmt_pct(float(summary.get('pass_rate', 0.0)))} |",
        f"| Mean score | {float(summary.get('mean_score', 0.0)):.3f} |",
        f"| p95 latency | {float(summary.get('p95_latency_ms', 0.0)):.0f} ms |",
        "",
        "## Score by tag",
        "",
        "| Tag | Passed | Mean score |",
        "| --- | ---: | ---: |",
    ]
    tags = summary.get("tags", [])
    if tags:
        for tag in tags:
            lines.append(
                f"| {_md_cell(tag.get('tag', ''))} | {int(tag.get('passed', 0))} / {int(tag.get('count', 0))} | "
                f"{float(tag.get('mean_score', 0.0)):.3f} |"
            )
    else:
        lines.append("| No tags | 0 / 0 | 0.000 |")
    lines.extend([
        "",
        "## Task results",
        "",
        "| Task | Status | Score | Latency | Attempts | Checks |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ])
    for result in results:
        checks = result.get("checks", [])
        check_text = "; ".join(
            f"{item.get('type')}: {item.get('detail')}" for item in checks
        ) or str(result.get("error") or "no checks recorded")
        lines.append(
            "| " + " | ".join([
                _md_cell(result.get("task_id", ""), 80),
                "PASS" if result.get("passed") else "FAIL",
                f"{float(result.get('score', 0.0)):.3f}",
                f"{float(result.get('latency_ms', 0.0)):.0f} ms",
                str(int(result.get("attempts", 1))),
                _md_cell(check_text, 160),
            ]) + " |"
        )
    return "\n".join(lines) + "\n"


def write_markdown(run_path: str, markdown_path: str) -> None:
    payload = load_run(run_path)
    path = Path(markdown_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8", newline="\n")


def render_compare_markdown(payload: dict[str, Any]) -> str:
    """Render a baseline/candidate comparison for CI job summaries."""
    summary = payload.get("summary", {})
    status = "PASS" if payload.get("ok") else "FAIL"
    lines = [
        "# EvalForge regression comparison",
        "",
        f"**Status:** {status}",
        "",
        f"**Baseline:** `{_md_cell(payload.get('baseline', ''), 160)}`",
        "",
        f"**Candidate:** `{_md_cell(payload.get('candidate', ''), 160)}`",
        "",
        f"**Allowed score drop:** {float(payload.get('max_drop', 0.0)):.3f}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Common tasks | {int(summary.get('common', 0))} |",
        f"| Regressions | {int(summary.get('regressions', 0))} |",
        f"| Improvements | {int(summary.get('improvements', 0))} |",
        f"| Unchanged | {int(summary.get('unchanged', 0))} |",
        f"| Missing in candidate | {int(summary.get('missing_in_candidate', 0))} |",
        f"| Added in candidate | {int(summary.get('added_in_candidate', 0))} |",
        f"| Mean score delta | {float(summary.get('mean_score_delta', 0.0)):+.3f} |",
        f"| Pass-rate delta | {_fmt_pct(float(summary.get('pass_rate_delta', 0.0)))} |",
    ]

    def add_changes(title: str, items: list[dict[str, Any]]) -> None:
        lines.extend([
            "",
            f"## {title}",
            "",
            "| Task | Baseline | Candidate | Delta | Baseline status | Candidate status |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ])
        if not items:
            lines.append("| None |  |  |  |  |  |")
            return
        for item in items:
            lines.append(
                "| " + " | ".join([
                    _md_cell(item.get("task_id", ""), 80),
                    f"{float(item.get('baseline_score', 0.0)):.3f}",
                    f"{float(item.get('candidate_score', 0.0)):.3f}",
                    f"{float(item.get('delta', 0.0)):+.3f}",
                    "PASS" if item.get("baseline_passed") else "FAIL",
                    "ERROR" if item.get("candidate_error") else ("PASS" if item.get("candidate_passed") else "FAIL"),
                ]) + " |"
            )

    add_changes("Regressions", payload.get("regressions", []))
    add_changes("Improvements", payload.get("improvements", []))
    lines.extend(["", "## Task set differences", ""])
    missing = payload.get("missing_in_candidate", [])
    added = payload.get("added_in_candidate", [])
    if not missing and not added:
        lines.append("Baseline and candidate contain the same task IDs.")
    else:
        if missing:
            lines.append("**Missing from candidate:** " + ", ".join(f"`{_md_cell(item, 80)}`" for item in missing))
        if added:
            lines.append("**Added in candidate:** " + ", ".join(f"`{_md_cell(item, 80)}`" for item in added))
    return "\n".join(lines) + "\n"


def write_compare_markdown(payload: dict[str, Any], markdown_path: str) -> None:
    path = Path(markdown_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_compare_markdown(payload), encoding="utf-8", newline="\n")


def render_junit(payload: dict[str, Any]) -> str:
    """Render a run payload as a JUnit XML test suite."""
    results = payload.get("results", [])
    failures = sum(1 for item in results if not item.get("passed") and not item.get("error"))
    errors = sum(1 for item in results if item.get("error"))
    total_seconds = sum(float(item.get("latency_ms", 0.0)) for item in results) / 1000.0
    suite = ET.Element(
        "testsuite",
        {
            "name": "evalforge",
            "tests": str(len(results)),
            "failures": str(failures),
            "errors": str(errors),
            "time": f"{total_seconds:.6f}",
            "timestamp": str(payload.get("created_at", "")),
        },
    )
    for result in results:
        tags = [str(tag) for tag in result.get("tags", [])]
        classname = "evalforge." + ".".join(tags) if tags else "evalforge"
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": classname,
                "name": str(result.get("task_id", "")),
                "time": f"{float(result.get('latency_ms', 0.0)) / 1000.0:.6f}",
            },
        )
        checks = result.get("checks", [])
        detail = "; ".join(
            f"{item.get('type')}: {item.get('detail')}" for item in checks
        )
        if result.get("error"):
            element = ET.SubElement(testcase, "error", {"message": str(result.get("error"))})
            element.text = detail or str(result.get("error"))
        elif not result.get("passed"):
            element = ET.SubElement(
                testcase,
                "failure",
                {"message": f"task {result.get('task_id', '')} failed"},
            )
            element.text = detail or "task failed"
    ET.indent(suite, space="  ")
    return "<?xml version='1.0' encoding='utf-8'?>\n" + ET.tostring(suite, encoding="unicode") + "\n"


def write_junit(run_path: str, junit_path: str) -> None:
    payload = load_run(run_path)
    path = Path(junit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_junit(payload), encoding="utf-8", newline="\n")


_SARIF_RUN_RULES = {
    "EVALFORGE_TASK_FAILED": {
        "id": "EVALFORGE_TASK_FAILED",
        "name": "EvalForgeTaskFailed",
        "shortDescription": {"text": "task failed one or more deterministic scoring checks"},
        "defaultConfiguration": {"level": "error"},
    },
    "EVALFORGE_ADAPTER_ERROR": {
        "id": "EVALFORGE_ADAPTER_ERROR",
        "name": "EvalForgeAdapterError",
        "shortDescription": {"text": "adapter command failed or timed out for a task"},
        "defaultConfiguration": {"level": "error"},
    },
}

_SARIF_COMPARE_RULES = {
    "EVALFORGE_REGRESSION": {
        "id": "EVALFORGE_REGRESSION",
        "name": "EvalForgeRegression",
        "shortDescription": {"text": "candidate score regressed beyond the allowed drop"},
        "defaultConfiguration": {"level": "error"},
    },
    "EVALFORGE_MISSING_TASK": {
        "id": "EVALFORGE_MISSING_TASK",
        "name": "EvalForgeMissingTask",
        "shortDescription": {"text": "baseline task is missing from the candidate run"},
        "defaultConfiguration": {"level": "warning"},
    },
}


def _sarif_result(rule_id: str, level: str, message: str, uri: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri.replace("\\", "/")},
                    "region": {"startLine": 1},
                }
            }
        ],
        "properties": properties,
    }


def _sarif_document(rules: dict[str, Any], results: list[dict[str, Any]], *, version: str, execution_successful: bool) -> str:
    used_rules = [rules[key] for key in sorted(rules) if any(item["ruleId"] == key for item in results)]
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "EvalForge",
                        "version": version,
                        "informationUri": "https://github.com/midya8/evalforge",
                        "rules": used_rules,
                    }
                },
                "results": results,
                "invocations": [{"executionSuccessful": execution_successful}],
            }
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_sarif(payload: dict[str, Any], *, version: str, run_path: str) -> str:
    """Render a run payload as a SARIF 2.1.0 log of failed tasks and adapter errors."""
    results: list[dict[str, Any]] = []
    clean = True
    for item in payload.get("results", []):
        task_id = str(item.get("task_id", ""))
        checks = item.get("checks", [])
        detail = "; ".join(f"{check.get('type')}: {check.get('detail')}" for check in checks)
        properties = {
            "task_id": task_id,
            "score": float(item.get("score", 0.0)),
            "latency_ms": float(item.get("latency_ms", 0.0)),
            "tags": [str(tag) for tag in item.get("tags", [])],
        }
        if item.get("error"):
            clean = False
            results.append(
                _sarif_result(
                    "EVALFORGE_ADAPTER_ERROR",
                    "error",
                    f"task {task_id}: adapter error: {item.get('error')}",
                    run_path,
                    properties,
                )
            )
        elif not item.get("passed"):
            clean = False
            message = f"task {task_id} failed"
            if detail:
                message = f"{message}: {detail}"
            results.append(
                _sarif_result("EVALFORGE_TASK_FAILED", "error", message, run_path, properties)
            )
    return _sarif_document(_SARIF_RUN_RULES, results, version=version, execution_successful=clean)


def render_compare_sarif(payload: dict[str, Any], *, version: str) -> str:
    """Render a comparison payload as a SARIF 2.1.0 log of regressions."""
    candidate_uri = str(payload.get("candidate", ""))
    results: list[dict[str, Any]] = []
    for item in payload.get("regressions", []):
        task_id = str(item.get("task_id", ""))
        message = (
            f"task {task_id}: score {float(item.get('baseline_score', 0.0)):.3f} -> "
            f"{float(item.get('candidate_score', 0.0)):.3f} ({float(item.get('delta', 0.0)):+.3f})"
        )
        if item.get("candidate_error"):
            message = f"{message}; candidate error: {item['candidate_error']}"
        results.append(
            _sarif_result(
                "EVALFORGE_REGRESSION",
                "error",
                message,
                candidate_uri,
                {
                    "task_id": task_id,
                    "baseline_score": float(item.get("baseline_score", 0.0)),
                    "candidate_score": float(item.get("candidate_score", 0.0)),
                    "delta": float(item.get("delta", 0.0)),
                },
            )
        )
    for task_id in payload.get("missing_in_candidate", []):
        results.append(
            _sarif_result(
                "EVALFORGE_MISSING_TASK",
                "warning",
                f"task {task_id}: present in baseline but missing from candidate run",
                candidate_uri,
                {"task_id": str(task_id)},
            )
        )
    return _sarif_document(
        _SARIF_COMPARE_RULES,
        results,
        version=version,
        execution_successful=bool(payload.get("ok")),
    )


def write_sarif(run_path: str, sarif_path: str) -> None:
    payload = load_run(run_path)
    path = Path(sarif_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sarif(payload, version=__version__, run_path=run_path), encoding="utf-8", newline="\n")


def write_compare_sarif(payload: dict[str, Any], sarif_path: str) -> None:
    path = Path(sarif_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_compare_sarif(payload, version=__version__), encoding="utf-8", newline="\n")
