# Paired comparison evidence

## Contract

The comparison is about supplied result rows. It cannot establish matching task definitions, correct scoring, independent sampling or model quality. Every matched record, including output/error/checks/tags/attempts/latency, is retained. Missing/added records remain inspectable. Stored summaries are ignored and rebuilt; unknown native metadata is preserved. Native loading validates the known run fields, not arbitrary metadata; it is not a general strict JSON serializer. Legacy optional record fields get defaults. Score and passed are independent evidence.

`compare` preserves the original binary64 score-drop/pass-loss/missing-task gate and classification precedence. Thus 0.95 - 1 can be below -0.05 even though displayed decimal values look equal. The inspector exposes that boundary rather than silently retuning the gate. Persistent failures/errors can be unchanged, and empty comparisons can pass without evidence. Native comparison is not restricted to the browser limits below.

The inspector/audit CLI accepts at most 12 results per side and eight matched ids. Scores, check scores and allowed drop must be in [0,1] on a .001 lattice (absolute tick tolerance 1e-10). IDs are nonblank unique ASCII strings <=64 characters; outputs <=2048, errors <=256; <=8 unique nonblank tags <=64; <=8 checks with type <=32, detail <=256. Latency is finite nonnegative <=1,000,000ms; attempts integer 1..100. Text uses printable ASCII plus tab/newline/CR. Unknown result/check fields are rejected here rather than discarded. Audit files are <=128KiB with duplicate keys and nonfinite JSON tokens rejected. UI parsers do not claim duplicate-object-key detection. These are bounded arithmetic fixtures, not production model evaluation limits.

## Arithmetic

For each common task i, d_i = candidate ticks - baseline ticks. Every subset of nonzero differences supplies one sign assignment; observed T = sum d_i. Exact two-sided p = count(|sum s_i d_i| >= |T|) / 2^m. Every mask, sign, contribution, total and inclusive extreme flag is exported. Factoring zero differences cancels a common factor; all ties have one empty assignment and p=1. No matched pairs is undefined, not p=1. This is a symmetric absolute-sum convention, not a claim that all two-sided permutation conventions agree.

This requires independent/exchangeable paired score differences or a valid within-pair randomized-label design. Equal ids alone provide neither. Task cherry-picking, repeated/dependent prompts, unequal scoring definitions, post-hoc selection and repeated benchmark testing affect inference. No multiplicity correction or automatic threshold is applied.

Exact McNemar separates both-pass/lost-pass/gained-pass/both-fail ids. For n discordants and k=min(lost,gained), p=min(1,2*sum(comb(n,j), j<=k)/2^n). All binomial rows are exposed. No discordants with pairs gives p=1, not equivalence; no pairs is undefined. It tests binary pass marginals, not the score mean. No inference result changes the regression gate.

## Original work and retained controls

`docs/original-sha256.json` fingerprints the original README, all 68 tests, task data, mock adapter and demo. The README is archived byte-for-byte as `docs/original-readme.md`. `docs/original-run.json` is the actual original six-task mock execution with unedited timings/platform/path; `docs/original-report.html` is its original renderer output and is byte-reproduced by the current renderer. It is synthetic, not a hosted model run. Controlled candidate replacement in fixtures is explicitly labelled, not passed off as another adapter execution.

`tools/build_audits.py` retains 24 full Python reports: empty/no overlap, all ties, loss/gain, discordant pass balance, tolerated score drop, binary64 boundary, cohort reversal, hostile text and `__proto__`, maximal eight pairs, original mock and controlled replacement. Fixtures retain all rows and null assignments, not selected screenshots. Independent JavaScript recomputes the entire tree. Tests compare every numeric/non-numeric leaf, every displayed pair/assignment/pass table/binomial row/raw record and chart dot, current JSON export, invalidation and mobile containment. Separate Python brute-force signs including zeros validate the factored implementation over all 780 short vectors. The test suite validates all small pass-count tables and the unchanged native gate against a seeded reference. These are correctness controls, not generalization results.

The installed-wheel check runs outside the checkout with isolated imports, verifies nine installed module origins and every retained audit, then exercises audit/mock adapter/comparison CLI and HTML/JUnit/Markdown/SARIF outputs. CI uses Python 3.10-3.13, actual headless Chrome and the installed wheel. Retained latency is not a benchmark; regeneration uses stored mock output, so it does not rerun that timed source execution. Score means use explicit ordered binary64 accumulation to avoid Python 3.12 summation changes; same-environment byte equality is not cross-platform determinism.

## Prior work

The harness and regression rule predate this update and are preserved/extended, not a new evaluation invention. Paired permutations and exact McNemar are established methods. The contribution here is complete paired/all-cohort gate evidence, bounded exhaustive arithmetic, an editable independent browser and full-record/display/export verification.

- [SciPy permutation_test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html): samples swaps labels within pairs; pairings tests a different null. Exhaustive versus randomized tails and float tie warnings. Our integer lattice is for inference only.
- [StatLab paired permutation tests](https://statlab.github.io/permute/user/one-sample.html): independent within-pair label randomization assumptions.
- [Statsmodels McNemar API](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html) and [implementation](https://www.statsmodels.org/stable/_modules/statsmodels/stats/contingency_tables.html): exact binomial, doubled lower tail capped at one.
- [Demsar, JMLR 2006](https://www.jmlr.org/papers/volume7/demsar06a/demsar06a.pdf): classifier comparison across datasets, units and multiple comparisons. Its experimental protocol is not claimed for these heterogeneous task fixtures.
- [Yeh, COLING 2000](https://aclanthology.org/C00-2137.pdf): statistical testing of NLP result differences. Not verification of this code or evidence of model gains.
- [SciPy paired permutation implementation discussion](https://github.com/scipy/scipy/pull/17030): existing implementation/performance prior art, not independent correctness evidence.

Sources read November 8, 2026. No external code, data or model outputs copied.
