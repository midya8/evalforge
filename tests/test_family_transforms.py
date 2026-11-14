"""Whole-report symmetries on a fixed, bounded shared-sign family."""
import copy
from fractions import Fraction as F
from itertools import permutations
import unittest

from evalforge.family import family_report


BASE = {
    "candidates": ["a", "b", "c"],
    "tasks": [
        {"id": "t0", "cluster": "u", "baseline": 500, "scores": [503, 498, 500]},
        {"id": "t1", "cluster": "v", "baseline": 500, "scores": [499, 504, 502]},
        {"id": "t2", "cluster": "u", "baseline": 500, "scores": [502, 501, 497]},
        {"id": "t3", "cluster": "w", "baseline": 500, "scores": [496, 501, 502]},
    ],
}


def rescale_report(report, factor):
    """Change score-unit fields, leaving orbit counts and tail flags alone."""
    r = copy.deepcopy(report)
    for t in r["input"]["tasks"]:
        t["scores"] = [500 + factor * (x - 500) for x in t["scores"]]
    for t in r["task_differences"]:
        t["scores"] = [500 + factor * (x - 500) for x in t["scores"]]
        t["deltas"] = [factor * x for x in t["deltas"]]
    for b in r["clusters"]:
        b["sum_deltas"] = [factor * x for x in b["sum_deltas"]]
    for c in r["columns"]:
        for k in ["observed_sum", "observed_absolute"]:
            c[k] *= factor
        c["mean_difference_ticks"] = str(F(c["mean_difference_ticks"]) * factor)
        for h in c["absolute_histogram"]:
            h["value"] *= factor
    r["observed_maximum"] *= factor
    for a in r["assignments"]:
        a["cluster_contributions"] = [[factor * x for x in row]
                                        for row in a["cluster_contributions"]]
        a["totals"] = [factor * x for x in a["totals"]]
        a["absolute"] = [factor * x for x in a["absolute"]]
        a["maximum"] *= factor
    for h in r["maximum_histogram"]:
        h["value"] *= factor
    return r


class FamilyTransformTests(unittest.TestCase):
    def test_candidate_permutations_and_positive_score_units(self):
        baseline = family_report(BASE)
        for order in permutations(range(3)):
            # Column order changes coordinates, not the shared cluster signs.
            x = copy.deepcopy(BASE)
            x["candidates"] = [BASE["candidates"][j] for j in order]
            for t, old in zip(x["tasks"], BASE["tasks"]):
                t["scores"] = [old["scores"][j] for j in order]
            expected = copy.deepcopy(baseline)
            expected["input"] = copy.deepcopy(x)
            expected["columns"] = [baseline["columns"][j] for j in order]
            for t in expected["task_differences"]:
                for key in ["scores", "deltas"]:
                    t[key] = [t[key][j] for j in order]
            for b in expected["clusters"]:
                b["sum_deltas"] = [b["sum_deltas"][j] for j in order]
            for a in expected["assignments"]:
                a["cluster_contributions"] = [[row[j] for j in order]
                                                for row in a["cluster_contributions"]]
                for key in ["totals", "absolute", "raw_tail", "max_tail"]:
                    a[key] = [a[key][j] for j in order]
            for factor in [1, 2, 7, 25]:
                with self.subTest(order=order, factor=factor):
                    scaled = copy.deepcopy(x)
                    for t in scaled["tasks"]:
                        t["scores"] = [500 + factor * (v - 500) for v in t["scores"]]
                    self.assertEqual(family_report(scaled), rescale_report(expected, factor))

    def test_inactive_cluster_doubles_counts_not_fractions(self):
        baseline = family_report(BASE)
        x = copy.deepcopy(BASE)
        x["tasks"].append({"id": "zero", "cluster": "z", "baseline": 250,
                           "scores": [250, 250, 250]})
        r = family_report(x)
        self.assertEqual(r["orbit_size"], 2 * baseline["orbit_size"])
        self.assertEqual(r["active_cluster_count"], baseline["active_cluster_count"])
        self.assertEqual(r["global_tail_count"], 2 * baseline["global_tail_count"])
        self.assertEqual(r["global_tail_fraction"], baseline["global_tail_fraction"])
        for got, old in zip(r["columns"], baseline["columns"]):
            for key in ["raw_tail_count", "max_tail_count"]:
                self.assertEqual(got[key], 2 * old[key])
            for key in ["raw_tail_fraction", "max_tail_fraction", "observed_sum"]:
                self.assertEqual(got[key], old[key])
            # An added zero-difference task still changes the task-weighted mean.
            self.assertEqual(F(got["mean_difference_ticks"]),
                             F(old["observed_sum"], len(x["tasks"])))
        for i, a in enumerate(r["assignments"]):
            old = baseline["assignments"][i % baseline["orbit_size"]]
            self.assertEqual(a["totals"], old["totals"])
            self.assertEqual(a["cluster_contributions"][:-1], old["cluster_contributions"])
            self.assertEqual(a["cluster_contributions"][-1], [0, 0, 0])
            for key in ["absolute", "maximum", "raw_tail", "max_tail", "global_tail"]:
                self.assertEqual(a[key], old[key])
        self.assertEqual(BASE["tasks"][0]["scores"], [503, 498, 500])
