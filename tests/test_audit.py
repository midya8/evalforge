import copy,contextlib,hashlib,io,itertools,json,math,random,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from evalforge.audit import audit_compare,load_spec
from evalforge.compare import compare_payloads,compare_runs
from evalforge.core import EvalForgeError,load_run,validate_run
from evalforge.cli import main
from evalforge.runner import run_suite
ROOT=Path(__file__).resolve().parents[1]
def row(i,s,p=True,**kw):return dict(task_id=i,score=s,passed=p,**kw)
def spec(b=None,c=None,d=0):return dict(baseline=b if b is not None else [row('a',.8)],candidate=c if c is not None else [row('a',.9)],max_drop=d)
class AuditTests(unittest.TestCase):
 def test_fixtures_and_original_hashes(self):
  f=json.loads((ROOT/'docs/audit.json').read_text());self.assertEqual(len(f['cases']),24)
  for c in f['cases']:self.assertEqual(audit_compare(c['report']['spec']),c['report'])
  for p,h in json.loads((ROOT/'docs/original-sha256.json').read_text()).items():self.assertEqual(hashlib.sha256((ROOT/('docs/original-readme.md' if p=='README.md' else p)).read_bytes()).hexdigest(),h,p)
 def test_every_small_sign_vector_against_cartesian_reference(self):
  checked=0
  for n in range(1,5):
   for ds in itertools.product([-2,-1,0,1,2],repeat=n):
    r=audit_compare(spec([row(str(i),.5) for i in range(n)],[row(str(i),.5+d/1000) for i,d in enumerate(ds)]))
    sums=[sum(d*s for d,s in zip(ds,ss)) for ss in itertools.product([-1,1],repeat=n)];obs=abs(sum(ds));p=sum(abs(v)>=obs for v in sums)/len(sums)
    self.assertEqual(r['sign_flip']['p_two_sided'],p);checked+=1
  self.assertEqual(checked,780)
 def test_every_small_pass_table_against_binomial_enumeration(self):
  for n in range(1,7):
   for lost in range(n+1):
    r=audit_compare(spec([row(str(i),.5,i<lost) for i in range(n)],[row(str(i),.5,i>=lost) for i in range(n)]))
    cut=min(lost,n-lost);lower=sum(sum(bits)<=cut for bits in itertools.product([0,1],repeat=n));self.assertEqual(r['mcnemar']['p_two_sided'],min(1,2*lower/2**n))
 def test_cohort_reversal(self):
  r=audit_compare(json.loads((ROOT/'examples/audit.json').read_text()))['comparison'];self.assertLess(r['summary']['mean_score_delta'],0);self.assertGreater(r['paired_summary']['mean_score_delta'],0);self.assertFalse(r['ok']);self.assertEqual(r['missing_in_candidate'],['missing-easy'])
 def test_no_pairs_is_undefined_not_no_difference(self):
  r=audit_compare(spec([],[]));self.assertIsNone(r['sign_flip']['p_two_sided']);self.assertIsNone(r['comparison']['paired_summary']['mean_score_delta']);self.assertTrue(r['comparison']['ok'])
 def test_all_ties_one_reduced_assignment(self):
  r=audit_compare(spec([row('a',.5)],[row('a',.5)]));self.assertEqual(r['sign_flip']['total'],1);self.assertEqual(r['sign_flip']['p_two_sided'],1);self.assertEqual(r['mcnemar']['p_two_sided'],1)
 def test_pass_and_score_are_separate(self):
  r=audit_compare(spec([row('a',.8,False)],[row('a',.79,True)],.05))['comparison'];self.assertEqual(r['witnesses'][0]['classification'],'improvements');self.assertTrue(r['ok'])
 def test_allowed_decline_is_unchanged_classification(self):
  r=audit_compare(spec([row('a',1)],[row('a',.96)],.05))['comparison'];self.assertEqual(r['witnesses'][0]['classification'],'unchanged');self.assertLess(r['witnesses'][0]['delta'],0)
 def test_binary_float_gate_preserved_not_integer_redefined(self):
  r=audit_compare(spec([row('a',1)],[row('a',.95)],.05))['comparison'];self.assertTrue(r['witnesses'][0]['score_drop']);self.assertEqual(r['witnesses'][0]['delta'],.95-1)
 def test_original_rule_on_seeded_scores(self):
  rng=random.Random(19)
  for _ in range(200):
   a,b=rng.randrange(1001)/1000,rng.randrange(1001)/1000;p,q=rng.choice([True,False]),rng.choice([True,False]);drop=rng.randrange(1001)/1000
   r=audit_compare(spec([row('a',a,p)],[row('a',b,q)],drop))['comparison'];self.assertEqual(r['ok'],not (b-a < -drop or p and not q))
 def test_id_order_and_full_raw_records(self):
  b=[row('__proto__',.8,output='<img src=x>',checks=[dict(type='exact',passed=True,score=1,detail='x')]),row('constructor',.5)]
  r=audit_compare(spec(b,list(reversed(b))));self.assertEqual(r['comparison']['witnesses'][0]['baseline']['output'],'<img src=x>');self.assertEqual(r['comparison']['witnesses'][0]['task_id'],'__proto__')
  native=compare_payloads({'results':[row('x',.5,provenance={'source':'unverified fixture'})]},{'results':[row('x',.6,extra=['retained'])]})
  self.assertEqual(native['witnesses'][0]['baseline']['provenance'],{'source':'unverified fixture'});self.assertEqual(native['witnesses'][0]['candidate']['extra'],['retained'])
 def test_invalid_profiles(self):
  cases=[{},None,{**spec(), 'extra':1},{**spec(), 'max_drop':None},{**spec(),'max_drop':.0001},spec([row('é',.2)],[]),spec([row('a',.1234)],[]),spec([row('a',.5)]*2,[]),spec([row('a',.2,tags=['x']*9)],[]),spec([row('a',.2,checks=[dict(type='x',score=1,passed=True,extra=1)])],[]),spec([row(str(i),.2) for i in range(9)],[row(str(i),.3) for i in range(9)])]
  for s in cases:
   with self.subTest(s=s),self.assertRaises(EvalForgeError):audit_compare(s)
 def test_loader_duplicate_nonfinite_and_size(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.json'
   for text in ['{"baseline":[],"baseline":[],"candidate":[]}','{"baseline":[],"candidate":[],"max_drop":NaN}',' '*131073,'{']:
    p.write_text(text)
    with self.assertRaises(EvalForgeError):load_spec(p)
 def test_cli_actual_export(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'out.json'
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(['audit','--spec',str(ROOT/'examples/audit.json'),'--json',str(p)]),0)
   self.assertEqual(json.loads(p.read_text()),audit_compare(json.loads((ROOT/'examples/audit.json').read_text())))
class RunValidationTests(unittest.TestCase):
 def test_duplicate_result_ids_rejected_before_map(self):
  with self.assertRaisesRegex(EvalForgeError,'Duplicate'):compare_payloads({'results':[row('a',.5),row('a',1)]},{'results':[]})
 def test_stored_summaries_are_recomputed(self):
  r=compare_payloads({'results':[row('a',.5)],'summary':{'mean_score':999}}, {'results':[row('a',.5)],'summary':{'mean_score':-999}});self.assertEqual(r['summary']['mean_score_delta'],0);self.assertEqual(r['recomputed_summaries']['baseline']['count'],1)
 def test_invalid_row_fields(self):
  cases=[None,{},row('',.5),row('a',float('nan')),row('a',float('inf')),row('a',True),row('a',2),row('a',.5,'false'),row('a',.5,latency_ms=-1),row('a',.5,attempts=1.5),row('a',.5,tags=['x','x']),row('a',.5,checks='x'),row('a',.5,checks=[{}]),row('a',.5,error={})]
  for r in cases:
   with self.subTest(r=r),self.assertRaises(EvalForgeError):validate_run({'results':[r]})
 def test_optional_legacy_fields_keep_defaults(self):
  r=validate_run({'results':[row('a',.5,False)]});self.assertEqual(r['results'][0]['attempts'],1);self.assertEqual(r['results'][0]['latency_ms'],0)
 def test_drop_rejects_nonfinite_boolean(self):
  for v in [float('nan'),float('inf'),True,-1,None]:
   with self.assertRaises(EvalForgeError):compare_payloads({'results':[]},{'results':[]},max_drop=v)
 def test_runtime_options_fail_before_adapter(self):
  for kw in [{'timeout':float('nan')},{'timeout':float('inf')},{'workers':True},{'workers':1.5},{'retries':False},{'retries':.5}]:
   with patch('evalforge.runner._run_once') as run,self.assertRaises(EvalForgeError):run_suite(ROOT/'examples/tasks.jsonl','mock',**kw)
   run.assert_not_called()
 def test_fail_under_invalid_does_not_write_or_run(self):
  with patch('evalforge.cli.run_suite') as run,contextlib.redirect_stderr(io.StringIO()):
   self.assertEqual(main(['run','--tasks','x','--cmd','x','--out','x','--fail-under','nan']),2);run.assert_not_called()
 def test_extreme_integer_options_domain_error(self):
  with self.assertRaises(EvalForgeError):compare_payloads({"results":[]},{"results":[]},max_drop=10**10000)
  with self.assertRaises(EvalForgeError):run_suite(ROOT/"examples/tasks.jsonl","mock",timeout=10**10000)
 def test_duplicate_task_tags_rejected_at_source(self):
  from evalforge.core import Task
  with self.assertRaises(EvalForgeError):Task.from_dict(dict(id="a",prompt="p",expected="x",tags=["x"," x "]))
 def test_invalid_utf8_run_is_domain_error(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';p.write_bytes(b'\xff')
   with self.assertRaises(EvalForgeError):load_run(p)
