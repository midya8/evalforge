"""Bounded exact clustered sign-flip family arithmetic.

Supplied scores/cluster labels do not prove joint symmetry or randomization.
This separate API never changes the original EvalForge regression gate.
"""
from copy import deepcopy
from fractions import Fraction
import re
from .core import EvalForgeError


def _fields(x, keys):
    if not isinstance(x, dict) or set(x) != set(keys):
        raise EvalForgeError('exact fields required: ' + ','.join(keys))


def _label(s):
    if not isinstance(s, str) or re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,23}', s, flags=re.ASCII) is None:
        raise EvalForgeError('labels need ASCII letter then letters/digits/_/-, at most 24 characters')
    return s


def _ticks(x):
    if type(x) is not int or not 0 <= x <= 1000:
        raise EvalForgeError('scores need integer ticks in 0..1000; floats and booleans rejected')
    return x


def normalize(request):
    _fields(request, ['candidates', 'tasks'])
    r = deepcopy(request)
    cols = r['candidates']
    if not isinstance(cols, list) or not 1 <= len(cols) <= 4:
        raise EvalForgeError('one to four candidate labels required')
    for c in cols:
        _label(c)
    if len(set(cols)) != len(cols):
        raise EvalForgeError('candidate labels must be distinct')
    tasks = r['tasks']
    if not isinstance(tasks, list) or len(tasks) > 12:
        raise EvalForgeError('at most twelve tasks')
    ids, clusters = set(), set()
    for t in tasks:
        _fields(t, ['id', 'cluster', 'baseline', 'scores'])
        _label(t['id']);_label(t['cluster'])
        if t['id'] in ids:
            raise EvalForgeError('task ids must be unique')
        ids.add(t['id']);clusters.add(t['cluster'])
        _ticks(t['baseline'])
        if not isinstance(t['scores'], list) or len(t['scores']) != len(cols):
            raise EvalForgeError('each task needs one score per candidate in listed order')
        for x in t['scores']:
            _ticks(x)
    if len(clusters) > 8:
        raise EvalForgeError('at most eight sign-flip clusters')
    return r


def family_report(request):
    r = normalize(request)
    cols, tasks = r['candidates'], r['tasks']
    clusters = sorted({t['cluster'] for t in tasks})
    deltas = [{'id': t['id'], 'cluster': t['cluster'], 'baseline': t['baseline'],
               'scores': t['scores'][:], 'deltas': [s-t['baseline'] for s in t['scores']]} for t in tasks]
    blocks = [{'cluster': b, 'task_ids': [t['id'] for t in tasks if t['cluster'] == b],
               'sum_deltas': [sum(t['deltas'][j] for t in deltas if t['cluster'] == b) for j in range(len(cols))]}
              for b in clusters]
    observed = [sum(t['deltas'][j] for t in deltas) for j in range(len(cols))]
    observed_abs = list(map(abs, observed))
    maximum = max(observed_abs)
    assignments = []
    for mask in range(1 << len(blocks)) if tasks else []:
        signs = [-1 if mask & (1 << i) else 1 for i in range(len(blocks))]
        contributions = [[signs[i]*d for d in b['sum_deltas']] for i, b in enumerate(blocks)]
        totals = [sum(v[j] for v in contributions) for j in range(len(cols))]
        absolute = list(map(abs, totals))
        mx = max(absolute)
        assignments.append({'mask': mask, 'signs': signs, 'cluster_contributions': contributions,
                            'totals': totals, 'absolute': absolute, 'maximum': mx,
                            'raw_tail': [v >= o for v, o in zip(absolute, observed_abs)],
                            'max_tail': [mx >= o for o in observed_abs], 'global_tail': mx >= maximum})
    den = len(assignments)
    def fraction(n):
        return str(Fraction(n, den)) if den else None
    columns = []
    for j, c in enumerate(cols):
        raw = sum(t['raw_tail'][j] for t in assignments)
        adj = sum(t['max_tail'][j] for t in assignments)
        counts = {}
        for t in assignments:
            v = t['absolute'][j]
            counts[v] = counts.get(v, 0)+1
        columns.append({'candidate': c, 'observed_sum': observed[j], 'observed_absolute': observed_abs[j],
                        'mean_difference_ticks': str(Fraction(observed[j], len(tasks))) if tasks else None,
                        'raw_tail_count': raw, 'max_tail_count': adj, 'raw_tail_fraction': fraction(raw),
                        'max_tail_fraction': fraction(adj),
                        'absolute_histogram': [{'value': v, 'count': counts[v]} for v in sorted(counts)]})
    maxcounts = {}
    for t in assignments:
        mx = t['maximum']
        maxcounts[mx] = maxcounts.get(mx, 0)+1
    family_count = sum(t['global_tail'] for t in assignments)
    return {'schema': 1, 'input': r, 'defined': bool(tasks), 'task_count': len(tasks),
            'cluster_count': len(blocks), 'orbit_size': den,
            'active_cluster_count': sum(any(b['sum_deltas']) for b in blocks),
            'task_differences': deltas, 'clusters': blocks, 'columns': columns,
            'observed_maximum': maximum, 'global_tail_count': family_count,
            'global_tail_fraction': fraction(family_count), 'assignments': assignments,
            'maximum_histogram': [{'value': v, 'count': maxcounts[v],
                                   'survival_count': sum(n for w, n in maxcounts.items() if w >= v),
                                   'survival_fraction': fraction(sum(n for w, n in maxcounts.items() if w >= v))}
                                  for v in sorted(maxcounts)],
            'limits': 'Supplied common-task integer scores and cluster labels; shared cluster signs across every candidate. Exact inclusive absolute-sum/max tails, not studentized tests, automatic gates, proven joint symmetry or universal strong-FWER/model-superiority claims.'}
