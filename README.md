# EvalForge

Local-first evaluation for LLM and agent outputs, with paired comparison evidence.

[Open the paired inspector](https://midya8.github.io/evalforge/) · [Evidence contract](EVIDENCE.md) · [Original README](docs/original-readme.md)

## Choose an evaluation

| Question | Entry point | Result |
| --- | --- | --- |
| Does an adapter satisfy the supplied checks? | `validate`, `run`, `report` | Per-task responses, scores, errors and report files |
| Which paired results changed? | `compare`, `audit`, `docs/index.html` | Matched deltas, regression decisions and bounded paired controls |
| How do shared cluster signs affect a candidate family? | `evalforge.family_cli`, `docs/family.html` | Complete joint sign orbit and maximum tails |

The original gate and statistical controls answer different questions. A passed
comparison is not an absolute quality verdict; matching task IDs or supplied
cluster labels do not establish the statistical assumptions.

## Paired task comparison

The original standard-library harness runs local/hosted command adapters, scores text with deterministic checks, preserves responses/errors/check details and writes HTML, JUnit, Markdown and SARIF reports. The included six-task adapter is an offline mock, not an AI model or benchmark.

Comparison now retains every matched task's full baseline/candidate records, score/pass changes, gate margin and decision. Means are recomputed from result rows, never trusted from stored summaries. The all-task delta and matched-task delta are separate: missing/added tasks can reverse their signs. Duplicate result ids, nonfinite/out-of-range scores, non-Boolean pass flags, invalid latency/attempts/check records and duplicate tags are rejected instead of silently coerced or overwritten.

The regression rule is preserved: fail when delta < -max_drop, a passing task becomes failing, or a baseline task is missing. Added candidate tasks do not fail it. A tolerated decline is classified "unchanged"; a persistent error/failure can still pass a comparison. This is not an absolute quality gate. Native comparison retains binary64 boundary behavior and is not restricted to the inspector's grid.

## Run the original harness

```bash
python -m evalforge validate examples/tasks.jsonl
python -m evalforge run --tasks examples/tasks.jsonl \
  --cmd "python examples/mock_model.py" --out run.json \
  --report report.html --junit results.xml --markdown summary.md \
  --sarif analysis.sarif --fail-under 1
python -m evalforge compare baseline.json candidate.json --max-drop .05 \
  --format json --markdown comparison.md --sarif comparison.sarif
python -m evalforge report run.json --html report.html
python -m evalforge audit --spec examples/audit.json --json audit.json
```

Adapters receive the prompt on stdin, write their answer to stdout, and may use EVALFORGE_TASK_ID/EVALFORGE_PROMPT. Adapter commands and task checks execute locally with the caller's permissions; EvalForge does not sandbox them. Review unfamiliar programs before running them. JSONL tasks use id/prompt and expected or checks. Checks: exact, contains, regex, JSON/subset, lexical token-F1, numeric tolerance, word/character length. Tags, timeouts, retries and bounded workers remain supported. Task loading validates structure; check-specific validation occurs when scoring. Invalid run gates and nonfinite/runtime options are now rejected before adapter execution.

Exit codes remain 0 for a passed configured gate, 1 for a failed evaluation/comparison gate, 2 for invalid inputs. The `audit` command exports valid evidence and returns 0 even when its described comparison gate fails. Statistical controls do not change CI decisions.

## Independent paired inspector

Edit both result lists and allowed drop. Every matched pair, missing/added id, raw record and chart dot is recomputed by independent scalar JavaScript. The chart uses a fixed 0..1 score axis. Export contains the actual current report; edits hide stale results until recomputed. Output is rendered as text, not HTML.

Two bounded statistical controls expose all arithmetic:

- **Paired sign flips:** enumerate every sign assignment of nonzero integer .001-score differences, retaining each contribution, sum and absolute-tail flag. Ties count in the two-sided tail; zero differences are factored out. No Monte Carlo or plus-one adjustment.
- **Exact McNemar:** expose all four paired pass-status cells, all binomial counts and the doubled/capped lower tail of discordant pairs. This tests pass marginals, not mean score.

No matched pairs is undefined; all ties give p=1, not equivalence. Independent/exchangeable pairs are assumptions, not facts established by equal ids. Repeated prompts, selected tasks, changed scorers and benchmark reuse can invalidate interpretation. No multiple-comparison correction, confidence interval, significance threshold, scientific verdict or automatic inference gate. These are arithmetic controls, not evidence of model superiority.

## Verification and retained work

- All 68 original tests, original task suite, mock adapter and demo are byte-preserved. The original captured six-task run and HTML report remain visible; the current renderer reproduces that HTML exactly.
- The paired-inspector release had 92 Python tests, including all 780 difference vectors of lengths 1..4 over {-2,-1,0,1,2} against a separate Cartesian sign enumeration, all small discordant pass counts, 200 seeded gate comparisons and malformed/stale run controls.
- 24 complete retained reports, independently compared at all 11,808 numeric and 2,691 other scalar leaves.
- Three Node/actual-Chrome tests verify 53 paired rows, 564 sign assignments, 118 full displayed records, 47 binomial rows, all chart points, pass tables, invalidation/export and 320/390/1280 containment.
- Python 3.10-3.13 test/regenerate fixtures. An isolated installed wheel outside the checkout verifies nine module origins, all reports and audit/adapter/compare CLI plus report formats.

Same-environment byte regeneration is not all-platform determinism. Retained latency values are one local execution, not a performance benchmark. Scores/pass flags are supplied evidence, not rescored here or authenticated. See [EVIDENCE.md](EVIDENCE.md) for the exact bounded schema, definitions, provenance and prior work.

```bash
python -m unittest discover -s tests -v
python tools/build_audits.py
npm test
bash examples/demo.sh
bash tools/wheel_smoke.sh
```

## Clustered joint family orbit (0.2)

[Inspect shared cluster signs and complete max tails](https://midya8.github.io/evalforge/family.html) or read [FAMILY.md](FAMILY.md). A separate bounded integer-score API and CLI enumerate every shared cluster sign across up to four candidates. The original regression gate, paired audit and McNemar paths are unchanged. Supplied labels do not establish joint symmetry; no universal strong-FWER or model-superiority claim.
The current suite has 102 Python tests and seven Node/actual-Chrome tests,
including the earlier paired checks. The family experiment has its own native
entry point and installed API/module/console reproduction:

```bash
python -m evalforge.family_cli --input examples/family.json
bash tools/family_wheel_smoke.sh
```
