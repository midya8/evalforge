"""Self-contained HTML reports for evaluation runs."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

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
