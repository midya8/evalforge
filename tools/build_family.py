"""Deterministic complete family reports and input-only browser controls."""
from pathlib import Path
import copy
import json
import random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalforge.family import family_report
ROOT = Path(__file__).resolve().parents[1]

def make(vectors, groups=None):
    n = len(vectors[0]) if vectors else 0
    return {'candidates': ['candidate_'+str(j) for j in range(len(vectors))],
            'tasks': [{'id': 'task_'+str(i), 'cluster': 'cluster_'+str(groups[i] if groups else i),
                       'baseline': 500, 'scores': [500+v[i] for v in vectors]} for i in range(n)]}

cases = [{'id': 'one-claim-becomes-a-family', 'input': make([[100,100,100],[-200,-200,100]])},
         {'id': 'repeated-prompts-three-signs', 'input': make([[100]*6,[-200]*4+[100]*2], [0,0,1,1,2,2])},
         {'id': 'same-six-rows-independent', 'input': make([[100]*6,[-200]*4+[100]*2])},
         {'id': 'all-rows-one-cluster', 'input': make([[100]*6,[-200]*4+[100]*2], [0]*6)},
         {'id': 'all-ties', 'input': make([[0]*4,[0]*4], [0,0,1,1])},
         {'id': 'cancel-within-cluster', 'input': make([[100,-100,200,-200],[10,-10,-30,30]], [0,0,1,1])},
         {'id': 'empty-evidence', 'input': {'candidates':['candidate_0'], 'tasks':[]}},
         {'id': 'one-task', 'input': make([[500],[-500],[0]])},
         {'id': 'identical-candidates', 'input': make([[100,200,-100,200]]*3)},
         {'id': 'opposite-candidates', 'input': make([[100,200,-100,200],[-100,-200,100,-200]])},
         {'id': 'unequal-cluster-sizes', 'input': make([[100]*6,[0,100,200,-100,300,-200]], [0,0,0,0,1,2])},
         {'id': 'max-boundary', 'input': make([[500,-500,0,500,-500,0,500,-500,0,500,-500,0],[-500,500,0,-500,500,0,-500,500,0,-500,500,0],[0]*12,[100]*12], [0,1,2,3,4,5,6,7,0,1,2,3])}]
rng = random.Random(812)
for i in range(12):
    n = rng.randint(2,8);m=rng.randint(1,4)
    vectors = [[rng.choice([-300,-100,0,100,300])for _ in range(n)]for _ in range(m)]
    groups = [rng.randrange(min(4,n))for _ in range(n)]
    cases.append({'id':'seeded_'+str(i),'input':make(vectors, groups)})
reports = [{'id':c['id'],'report':family_report(c['input'])}for c in cases]
(ROOT/'examples/family.json').write_text(json.dumps(cases[0]['input'],indent=2)+'\n')
(ROOT/'examples/family-reports.json').write_text(json.dumps(reports,separators=(',',':'))+'\n')
(ROOT/'docs/family-data.js').write_text('window.FamilyInputs='+json.dumps(cases,separators=(',',':'))+';\n')
print(json.dumps({'reports':len(reports),'tasks':sum(len(c['report']['task_differences'])for c in reports),
                  'assignments':sum(len(c['report']['assignments'])for c in reports),
                  'contributions':sum(len(a['signs'])*len(c['report']['columns'])for c in reports for a in c['report']['assignments'])}))
