# Clustered joint sign-flip family audit

EvalForge 0.2 adds a separate, dependency-free exact arithmetic experiment. It does **not** change the original binary64 regression gate, paired audit, McNemar calculation, scorer, adapter or original CLI commands.

[Open the family inspector](https://midya8.github.io/evalforge/family.html). Original inspector: https://midya8.github.io/evalforge/.

## Why this exists

An evaluation may repeat prompts from the same source and compare several model candidates against one baseline. Treating every row as an independent sign, or flipping each candidate separately, silently changes the experiment. This inspector lets you inspect a declared cluster sign action, shared across every candidate, and the complete maximum-statistic distribution. It does not infer the correct clustering.

The bundled default has three task differences `[100,100,100]` for candidate 0 and `[-200,-200,100]` for candidate 1. Candidate 0 has absolute sum 300. Its raw inclusive tail is 2/8 = **1/4**, but the family-maximum tail at the same threshold is 4/8 = **1/2**. This synthetic arithmetic example is not a model benchmark or a claim of superiority.

A second control duplicates each row within its cluster. The same six rows yield 8 signs and raw tail 1/4 when grouped in pairs, 64 signs and raw tail 1/32 when treated independently, and 2 signs and raw tail 1 when all share a cluster. These are different declared null actions, not competing estimates of the correct answer.

## Contract

- Input has exactly `candidates` and `tasks`. Candidate labels are distinct, 1-4 entries. Each task has exactly `id`, `cluster`, `baseline`, `scores`.
- At most 12 matched tasks and 8 distinct clusters. IDs are unique. Labels start with an ASCII letter, followed by ASCII letters/digits/underscore/hyphen, at most 24 characters.
- Baseline and candidate scores are integer ticks in 0..1000 on one common scale. Every task supplies every candidate score. Scores are not rounded from original EvalForge runs.
- Browser/CLI JSON rejects duplicate keys, decimal/exponent/negative numeric spellings, booleans as scores, oversized input (>128 KiB) and nesting deeper than 8. The Python object API accepts actual Python integers, not bools/floats; lexical spelling is a JSON boundary concern.
- Each task contributes `candidate_score - baseline_score`. Clusters sum their original task differences. Unequal clusters therefore retain **task weighting**, not equal-cluster weighting.
- Sorted cluster labels fix sign order. The unflipped assignment is mask 0. Bit i set means cluster i gets sign -1; otherwise +1. The same sign applies to every task and candidate within that cluster.
- Every one of the `2^G` sign vectors is retained, including all-zero blocks and duplicate resulting totals. No distinct-total shortcut drops multiplicity.
- For candidate j: `T_j(s) = abs(sum_b s_b * sum_{i in b} delta_ij)`. `M(s) = max_j T_j(s)`. Raw tails count `T_j(s) >= T_j(+)`; max tails count `M(s) >= T_j(+)`; the global tail counts `M(s) >= M(+)`. All use the complete orbit denominator and reduced exact fractions.
- This explicitly uses inclusive **absolute-sum tails**. It is not twice the smaller one-sided tail, a studentized statistic, a mid-p calculation or a Monte Carlo estimate. No randomized-test +1 correction is added to an exhaustive orbit.
- An empty task list has no evidential orbit in this API: zero assignments and undefined/null tails and means. All-zero nonempty evidence retains its full orbit and tails of 1. Neither proves equivalence.

## What the assumptions do, and do not, say

For a probability interpretation of these joint-null orbit tails, the full matrix of task difference vectors must have a distribution invariant under the declared independent cluster sign flips, or a valid experimental randomization must justify the same transformation distribution. This is an assumption about data generation, not a property verified by the code. Cluster labels alone do not establish independent clusters, central symmetry, exchangeability, randomization, representative evaluation tasks or independence from model selection.

Marginal symmetry of each candidate is not enough to justify the **joint** maximum distribution. A shared baseline makes separate, independent candidate flips especially inappropriate. The Python test's direct original-task relabeling is an independent arithmetic reference, not evidence that simultaneous candidate/baseline relabeling was a real experiment.

Under uniform sampling over a declared finite sign orbit, the inclusive global tail has the finite-orbit superuniform rank property, accounting for ties. Tests check that algebraic property. They do not prove that real scores were sampled that way. Under a justified complete joint null this supports a complete-null/global test interpretation and corresponding complete-null family protection. It is **not** a universal strong-FWER guarantee under arbitrary partial nulls. We do not claim that subset pivotality is always necessary, nor that merely naming it verifies a joint-null assumption. No automatic acceptance/rejection, individual superiority, causal, confidence-interval or equivalence claim is emitted.

The paper examples below describe richer GLM/block/permutation frameworks. This project implements only the declared bounded sign-vector arithmetic. In particular, allowing unequal cluster sizes here is not a claim to reproduce whole-block exchangeability designs that require equal-size blocks.

## Reproduce

```sh
python -m unittest discover -s tests -v
python tools/build_family.py
python -m evalforge.family_cli --input examples/family.json > /tmp/family-report.json
python -m pip install .
evalforge-family --input examples/family.json
npm test
bash tools/wheel_smoke.sh
bash tools/family_wheel_smoke.sh
```

```python
from evalforge import family_report
report = family_report({
    'candidates': ['model_a', 'model_b'],
    'tasks': [
        {'id': 'prompt_0', 'cluster': 'source_0', 'baseline': 500, 'scores': [600, 300]},
        {'id': 'prompt_1', 'cluster': 'source_1', 'baseline': 500, 'scores': [600, 300]},
        {'id': 'prompt_2', 'cluster': 'source_2', 'baseline': 500, 'scores': [600, 600]},
    ],
})
assert report['columns'][0]['max_tail_fraction'] == '1/2'
```

Native implementation aggregates cluster differences and iterates bit masks. The independent browser implementation constructs Cartesian sign vectors and sums original task differences. A second Python reference relabels original candidate/baseline values per task and cluster. Tests compare every field of all 24 saved complete reports; 150 seeded cases and all 729 two-candidate/three-cluster difference matrices over {-1,0,1} check the independent reference. Real Chrome checks every displayed task, cluster, candidate, histogram and assignment row, bar geometry, stale-state clearing, invalid input, both JSON exports and 320/390/1280px overflow. Exported input/report contain user-supplied values and the full arithmetic, not screenshots or model calls.

## Sources and attribution

Original implementation and synthetic fixtures; no external code or data copied. These sources inform the statistical limits, not a claim of a new statistical method:

- [SciPy permutation_test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html): paired transformation choices, exhaustive vs randomized tests and non-universal two-sided conventions.
- [StatLab one-sample/paired permutation tutorial](https://statlab.github.io/permute/user/one-sample.html): assignment interpretation of paired sign flips.
- [Winkler et al., Permutation inference for the general linear model (2014)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4010955/): sign-flipping, dependence blocks and maximum statistics in a broader GLM setting.
- [Winkler et al., Multi-level block permutation (2015)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4644991/): dependence restrictions and symmetry assumptions.
- [Westfall and Troendle, Multiple Testing with Minimal Assumptions (2008)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3117234/): marginal exchangeability does not imply joint exchangeability; section 4 distinguishes the joint assumption from subset pivotality.
- [Rempala and Yang, On permutation procedures for strong control in multiple testing with gene expression data (2013)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3873102/): validity and strong-control conditions need careful specification.
- [multitestr package vignette](https://fdhidalgo.github.io/multitestr/articles/multitestr.html): supporting definitions of strong FWER and joint subset conditions.
