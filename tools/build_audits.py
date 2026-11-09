"""Retain complete controls. Original model is explicitly a local mock adapter."""
import copy,json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evalforge.audit import audit_compare
ROOT=Path(__file__).resolve().parents[1]
def row(k,s,p=True,**kw):return dict(task_id=k,score=s,passed=p,**kw)
def build():
 out=[]
 def add(name,b,c,drop=0):
  spec={"baseline":b,"candidate":c,"max_drop":drop};out.append({"name":name,"report":audit_compare(spec)})
 add('Cohort reversal',[row('a',.8),row('b',.8),row('missing-easy',1)],[row('a',.9),row('b',.9),row('added-hard',0,False)])
 add('Loss hidden by gains',[row('a',1),row('b',0,False),row('c',0,False)],[row('a',0,False),row('b',1),row('c',1)])
 add('Allowed decline',[row('a',1)],[row('a',.96)],.05)
 add('Passing status lost within tolerance',[row('a',1)],[row('a',.99,False)],.05)
 add('Pass regained despite lower score',[row('a',.8,False)],[row('a',.79)],.05)
 add('Binary64 boundary',[row('a',1)],[row('a',.95)],.05)
 add('Eight positive differences',[row(str(k),.2,False) for k in range(8)],[row(str(k),.8) for k in range(8)])
 add('Eight negative differences',[row(str(k),.8) for k in range(8)],[row(str(k),.2,False) for k in range(8)])
 add('Opposite changes cancel',[row('a',.2,False),row('b',.8)],[row('a',.8),row('b',.2,False)])
 add('Unequal changes',[row('a',.1,False),row('b',.3,False),row('c',.9)],[row('a',.9),row('b',.8),row('c',.7)])
 add('All ties',[row('a',.5,False),row('b',1)],[row('b',1),row('a',.5,False)])
 add('No common tasks',[row('a',1)],[row('b',1)])
 add('Empty runs',[],[])
 add('Missing run',[row('a',1)],[])
 add('Candidate-only data',[],[row('a',1)])
 add('Persistent errors',[row('a',0,False,error='exit 7')],[row('a',0,False,error='exit 9')])
 add('New error',[row('a',1)],[row('a',0,False,error='timeout')])
 add('Millipoint gains',[row('a',.499,False),row('b',.699,False)],[row('a',.5,False),row('b',.7,False)])
 add('Literal identifiers',[row('__proto__',.5),row('constructor',.6)],[row('constructor',.7),row('__proto__',.4)])
 add('HTML remains data',[row('a',.5,False,output='<img src=x onerror=alert(1)>',tags=['html'])],[row('a',.6,False,output='<script>not executed</script>',tags=['html'])])
 add('Tag and latency changes',[row('a',.5,False,latency_ms=900,tags=['old'],attempts=3)],[row('a',.5,False,latency_ms=10,tags=['new'])])
 add('Large allowed decline',[row('a',1)],[row('a',0)],1)
 original=json.loads((ROOT/'docs/original-run.json').read_text())['results']
 add('Original six-task mock',copy.deepcopy(original),copy.deepcopy(original))
 cand=copy.deepcopy(original);cand[0].update(score=0,passed=False,output='{}');cand[0]['checks']=[dict(type='json',score=0,passed=False,detail='controlled replacement, not a new adapter run')]
 add('Original mock with controlled replacement',copy.deepcopy(original),cand)
 return {'schema_version':1,'cases':out}
if __name__=='__main__':
 result=build();p=ROOT/'docs/audit.json';p.write_text(json.dumps(result,separators=(',',':'),sort_keys=True,allow_nan=False)+'\n');print('Retained',len(result['cases']),'reports',p.stat().st_size,'bytes')
 (ROOT/'examples/audit.json').write_text(json.dumps(result['cases'][0]['report']['spec'],indent=2)+'\n')
