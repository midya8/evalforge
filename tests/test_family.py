import copy
from fractions import Fraction as F
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from evalforge.family import family_report, normalize
from evalforge.family_cli import loads
from evalforge.core import EvalForgeError
ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT/'examples/family.json').read_text())


def reference(x):
    # Directly relabel every original task, not producer block sums/mask logic.
    blocks = sorted({t['cluster']for t in x['tasks']})
    result = []
    if x['tasks']:
        for labels in itertools.product([1,-1], repeat=len(blocks)):
            signs = dict(zip(blocks, labels))
            sums = []
            for j in range(len(x['candidates'])):
                candidate, baseline = 0, 0
                for task in x['tasks']:
                    b, c = task['baseline'], task['scores'][j]
                    if signs[task['cluster']] < 0:b,c=c,b
                    baseline += b;candidate += c
                sums.append(candidate-baseline)
            result.append((labels, sums))
    return result


class FamilyTests(unittest.TestCase):
    def test_default_family_control(self):
        r=family_report(BASE)
        self.assertEqual(r['columns'][0]['raw_tail_fraction'],'1/4')
        self.assertEqual(r['columns'][0]['max_tail_fraction'],'1/2')
        self.assertEqual(r['global_tail_fraction'],'1/2')
        self.assertEqual(r['orbit_size'],8)
        self.assertEqual(r['assignments'][0]['totals'],[300,-300])

    def test_independent_original_task_relabeling(self):
        rng=random.Random(211)
        for case in range(150):
            n=rng.randrange(9);m=rng.randint(1,4)
            x={'candidates':['c'+str(j)for j in range(m)],'tasks':[]}
            for i in range(n):
                x['tasks'].append({'id':'t'+str(i),'cluster':'b'+str(rng.randrange(max(1,min(n,5)))),
                                   'baseline':rng.randint(0,1000),'scores':[rng.randint(0,1000)for _ in range(m)]})
            r=family_report(x);ref=reference(x)
            lookup={tuple(a['signs']):a for a in r['assignments']}
            for signs, sums in ref:
                a=lookup[signs];self.assertEqual(a['totals'],sums)
                self.assertEqual(a['maximum'],max(map(abs,sums)))
                for j in range(m):
                    self.assertEqual(a['raw_tail'][j],abs(sums[j])>=r['columns'][j]['observed_absolute'])
                    self.assertEqual(a['max_tail'][j],max(map(abs,sums))>=r['columns'][j]['observed_absolute'])
            for j,c in enumerate(r['columns']):
                raw=sum(abs(s[j])>=c['observed_absolute']for _,s in ref)
                adj=sum(max(map(abs,s))>=c['observed_absolute']for _,s in ref)
                self.assertEqual(c['raw_tail_count'],raw);self.assertEqual(c['max_tail_count'],adj)
                self.assertEqual(c['raw_tail_fraction'],str(F(raw,len(ref)))if ref else None)
                self.assertGreaterEqual(adj,raw)
            self.assertEqual(sum(h['count']for h in r['maximum_histogram']),r['orbit_size'])

    def test_full_orbit_rank_superuniformity_under_declared_orbit(self):
        # Finite conditional orbit fact only. Does NOT prove input-generating symmetry.
        for x in [BASE]+[c['report']['input']for c in json.loads((ROOT/'examples/family-reports.json').read_text())[:12]]:
            orbit=reference(x)
            if not orbit:continue
            maxima=[max(map(abs,s))for _,s in orbit]
            tails=[sum(v>=u for v in maxima)for u in maxima]
            for cutoff in range(len(orbit)+1):
                self.assertLessEqual(sum(t<=cutoff for t in tails),cutoff)

    def test_grouping_changes_orbit_not_task_weighting(self):
        saved=json.loads((ROOT/'examples/family-reports.json').read_text())
        grouped=saved[1]['report'];free=saved[2]['report'];one=saved[3]['report']
        self.assertEqual(grouped['columns'][0]['observed_sum'],free['columns'][0]['observed_sum'])
        self.assertEqual(grouped['columns'][0]['raw_tail_fraction'],'1/4')
        self.assertEqual(free['columns'][0]['raw_tail_fraction'],'1/32')
        self.assertEqual(one['columns'][0]['raw_tail_fraction'],'1')
        self.assertEqual([grouped['orbit_size'],free['orbit_size'],one['orbit_size']],[8,64,2])
        # All rows in each block share a sign, but unequal blocks retain row weighting.
        unequal=saved[10]['report']
        self.assertEqual(unequal['clusters'][0]['sum_deltas'][0],400)
        self.assertEqual(unequal['columns'][0]['mean_difference_ticks'],'100')

    def test_zero_clusters_and_empty_are_not_equivalence(self):
        saved=json.loads((ROOT/'examples/family-reports.json').read_text())
        for i in [4,5]:
            r=saved[i]['report'];self.assertEqual(r['active_cluster_count'],0)
            self.assertEqual(r['orbit_size'],4)
            self.assertTrue(all(c['max_tail_fraction']=='1'for c in r['columns']))
        r=family_report({'candidates':['c'],'tasks':[]})
        self.assertFalse(r['defined']);self.assertIsNone(r['global_tail_fraction'])
        self.assertEqual(r['assignments'],[])

    def test_family_extension_monotonicity_same_units(self):
        for c in json.loads((ROOT/'examples/family-reports.json').read_text()):
            x=c['report']['input']
            for j in range(len(x['candidates'])):
                single={'candidates':[x['candidates'][j]],'tasks':[{**t,'scores':[t['scores'][j]]}for t in x['tasks']]}
                small=family_report(single)['columns'][0]
                self.assertEqual(small['raw_tail_fraction'],c['report']['columns'][j]['raw_tail_fraction'])
                self.assertEqual(small['raw_tail_fraction'],small['max_tail_fraction'])
                self.assertLessEqual(small['max_tail_count'],c['report']['columns'][j]['max_tail_count'])

    def test_saved_reports_and_input_purity(self):
        for c in json.loads((ROOT/'examples/family-reports.json').read_text()):
            x=c['report']['input'];old=copy.deepcopy(x)
            self.assertEqual(family_report(x),c['report']);self.assertEqual(x,old)
            self.assertEqual(normalize(normalize(x)),x)

    def test_bounds_and_strict_input(self):
        for change in [dict(candidates=[]),dict(candidates=['c']*2),dict(candidates=['<script>']),dict(tasks={}),dict(tasks=[{}])]:
            with self.assertRaises(EvalForgeError):family_report({**BASE,**change})
        for field,value in [('id',''),('cluster','bad label'),('baseline',True),('baseline',2.0),('baseline',1001),('scores',[500])]:
            x=copy.deepcopy(BASE);x['tasks'][0][field]=value
            with self.assertRaises(EvalForgeError):family_report(x)
        x=copy.deepcopy(BASE);x['tasks'][1]['id']=x['tasks'][0]['id']
        with self.assertRaises(EvalForgeError):family_report(x)
        x={'candidates':['c'],'tasks':[{'id':'t'+str(i),'cluster':'b'+str(i),'baseline':0,'scores':[0]}for i in range(9)]}
        with self.assertRaises(EvalForgeError):family_report(x)
        for text in ['{"x":1,"x":2}','-0','2.0','1e0','NaN','['*10+'0'+']'*10,' '*131073]:
            with self.assertRaises((EvalForgeError,ValueError)):loads(text)

    def test_cli_exports_errors_without_execution(self):
        for text in [json.dumps(BASE),'{"x":1,"x":2}','1e0',json.dumps({**BASE,'unknown':0})]:
            p=subprocess.run([sys.executable,'-m','evalforge.family_cli','--input','-'],input=text,text=True,capture_output=True)
            if text==json.dumps(BASE):self.assertEqual(p.returncode,0);self.assertEqual(json.loads(p.stdout),family_report(BASE))
            else:self.assertEqual(p.returncode,2);self.assertEqual(p.stdout,'');self.assertIn('family error',p.stderr)

    def test_exhaustive_short_multicolumn_sign_laws(self):
        for values in itertools.product([-1,0,1],repeat=6):
            x={'candidates':['a','b'],'tasks':[{'id':'t'+str(i),'cluster':'b'+str(i),'baseline':500,'scores':[500+values[i],500+values[3+i]]}for i in range(3)]}
            r=family_report(x);ref=reference(x);observed=[abs(sum(values[:3])),abs(sum(values[3:]))]
            for j in range(2):
                self.assertEqual(r['columns'][j]['raw_tail_count'],sum(abs(v[j])>=observed[j]for _,v in ref))
                self.assertEqual(r['columns'][j]['max_tail_count'],sum(max(map(abs,v))>=observed[j]for _,v in ref))
