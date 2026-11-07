# EvalForge

Local-first evaluation for LLM and agent outputs.

EvalForge runs a versioned set of prompts through any model or agent adapter you choose, scores every response with deterministic checks, writes a durable JSON run record, renders self-contained HTML, JUnit XML and Markdown reports, and compares candidate runs against a baseline so regressions fail before they ship.

It is deliberately useful without an API key: the included demo uses a deterministic local adapter, and the same runner can point at a local model, an internal agent binary, or a paid API command that the user separately configures.

## Why this exists

AI features often fail in ways that ordinary unit tests miss: a prompt edit improves one answer and silently regresses three others, a model swap changes output shape, or a latency spike only appears in a long tail. EvalForge makes those changes reviewable:

- prompts and acceptance criteria live in versioned JSONL;
- the adapter is just a command, so the harness does not care which model or agent runtime produced the text;
- checks are deterministic and inspectable rather than another opaque model judging the output;
- every run preserves raw output, check detail, latency, attempts and errors;
- baseline comparison produces a regression gate that CI can enforce.

## Features

- **Command adapter contract** — the task prompt is sent to the adapter on stdin, the adapter writes its answer to stdout, and non-zero exits are preserved as run errors.
- **Typed task suites** — JSONL tasks with stable IDs, prompts, expected values, tags, metadata and executable checks.
- **Deterministic scorers** — exact match, substring checks, regular expressions, JSON equality or subset matching, token-F1 similarity, numeric tolerance, and word/character length bounds.
- **Run records as artifacts** — JSON output includes per-task scores, check details, raw output, latency, attempts, adapter command, timestamp and tag roll-ups; JUnit XML exposes the same results to ordinary CI test viewers; Markdown run and regression summaries fit native CI job-summary surfaces.
- **Regression comparison** — compares a candidate run to a baseline by task ID, reports missing tasks and score drops first, and exits non-zero when the candidate regresses.
- **Self-contained reports** — one HTML file with inline CSS, escaped model output, summary cards, tag roll-ups and per-task details; no JavaScript or external assets.
- **Scriptable gates** — meaningful exit codes, `--fail-under`, `--max-drop`, tag filtering, retries, timeouts and bounded parallel execution.
- **Standard library only** — Python 3.10+ with no package dependencies, making the project easy to audit and run in constrained environments.

## Quick start

```bash
python3 -m evalforge validate examples/tasks.jsonl
python3 -m evalforge run \
  --tasks examples/tasks.jsonl \
  --cmd "python3 examples/mock_model.py" \
  --out .evalforge-demo/run.json \
  --report .evalforge-demo/report.html \
  --junit .evalforge-demo/results.xml \
  --markdown .evalforge-demo/summary.md \
  --fail-under 1.0
```

Expected result:

```text
6/6 passed · mean score 1.000 · errors 0 · p95 <latency> ms
```

Open `.evalforge-demo/report.html` for the rendered report. `.evalforge-demo/results.xml` is a JUnit report for CI test viewers, and `.evalforge-demo/summary.md` is a native CI job summary. The mock adapter is a deterministic stand-in, not an AI model; it proves the evaluation loop without pretending to measure model quality.

## Evaluate a real model or agent

Create a command that reads a prompt from stdin and writes the answer to stdout:

```bash
python3 -m evalforge run \
  --tasks tasks/production-agent.jsonl \
  --cmd "python3 adapters/my_agent.py --model candidate" \
  --out runs/candidate.json \
  --report reports/candidate.html \
  --timeout 45 \
  --retries 1 \
  --workers 2
```

The runner also exposes `EVALFORGE_TASK_ID` and `EVALFORGE_PROMPT` to the adapter environment. Raw stdout is stored as the response; stderr is preserved in the run error when the command exits non-zero.

## Task file format

Each non-empty line is one JSON object:

```json
{"id":"extract-city-json","prompt":"Return JSON for a Toronto weather lookup in metric units.","expected":{"city":"Toronto","units":"metric"},"tags":["extraction","json"]}
```

Required fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable unique task ID. Baseline comparisons match on this value. |
| `prompt` | Text sent to the adapter on stdin. |
| `expected` or `checks` | The acceptance criteria to execute. |

Optional `tags` drive filtered runs and per-tag roll-ups. Optional `metadata` stays in the task file for reviewer context.

When `checks` is omitted, EvalForge derives a sensible default from `expected`: JSON values use JSON equality, numbers use numeric matching, and strings use normalized exact matching. Explicit checks are better for production suites.

## Scorers

| Type | Example | Behavior |
| --- | --- | --- |
| `exact` | `{ "type": "exact", "value": "billing" }` | Whitespace-normalized match; case-sensitive only when requested. |
| `contains` | `{ "type": "contains", "all_of": ["raw output", "baseline"] }` | Requires one value, every item in `all_of`, or any item in `any_of`. |
| `regex` | `{ "type": "regex", "pattern": "p95 under 500 ms" }` | Searches the output with optional case-insensitive matching. |
| `json` | `{ "type": "json", "value": {"ok": true}, "subset": true }` | Parses output as JSON and requires exact or recursive subset equality. |
| `similarity` | `{ "type": "similarity", "value": "reference answer", "threshold": 0.8 }` | Token F1 against a reference with a configurable threshold. |
| `numeric` | `{ "type": "numeric", "value": 42, "tolerance": 0.1 }` | Extracts the first number and applies absolute or relative tolerance. |
| `length` | `{ "type": "length", "unit": "words", "min": 8, "max": 35 }` | Bounds word or character count. |

Invalid task definitions fail before any adapter command runs. Unsupported check types, malformed regexes and invalid JSONL are reported with the task ID or line number.

## Regression gates

Save a known-good run as the baseline, then compare every candidate:

```bash
python3 -m evalforge compare runs/baseline.json runs/candidate.json --max-drop 0.05
```

The comparison:

- matches results by stable task ID;
- reports regressions before improvements;
- treats missing candidate tasks as failures;
- includes mean-score and pass-rate deltas;
- exits `1` when a task drops more than `--max-drop`, a passing task starts failing, or a baseline task is missing;
- emits JSON with `--format json` for automation;
- writes a Markdown comparison with `--markdown PATH` for CI job summaries.

## Command reference

```text
python3 -m evalforge validate TASKS.jsonl
python3 -m evalforge run --tasks TASKS.jsonl --cmd COMMAND --out RUN.json [--report REPORT.html] [--junit RESULTS.xml] [--markdown SUMMARY.md]
                         [--timeout SECONDS] [--retries N] [--workers N]
                         [--tag TAG ...] [--fail-under SCORE]
python3 -m evalforge report RUN.json --html REPORT.html
python3 -m evalforge compare BASELINE.json CANDIDATE.json [--max-drop SCORE] [--format text|json] [--markdown COMPARISON.md]
```

Exit codes:

- `0` — command succeeded and all configured gates passed;
- `1` — an evaluation gate or regression comparison failed;
- `2` — invalid task file, run file or command-line input.

## Design notes

- **No hidden model dependency:** EvalForge evaluates the adapter you point it at. It does not bundle a proprietary model, call a paid API or require credentials.
- **Raw evidence first:** raw outputs and adapter errors are kept alongside scores, so a report never hides the response behind a single number.
- **Deterministic scoring:** checks run locally and produce the same result for the same output. This keeps CI stable and review discussions concrete.
- **Safe reporting:** generated HTML escapes all model output and carries its CSS inline. There are no external scripts, trackers or assets.
- **Standard-library architecture:** the code is split into small modules for task loading, scoring, execution, comparison, reporting and CLI behavior.

## Limitations

- Token-F1 similarity is a lexical check, not semantic judgment. Use exact, JSON, regex or numeric checks when correctness is precise.
- Parallel execution is bounded by `--workers`; hosted model adapters can still impose their own rate limits and costs.
- EvalForge records and gates behavior. It does not claim that a passing suite proves an AI system is safe or correct outside the tasks represented in that suite.

## Development

```bash
python3 -m unittest discover -s tests -v
bash examples/demo.sh
```

The test suite runs fully offline. CI runs the same suite on Python 3.10 through 3.13.
