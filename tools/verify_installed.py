"""Run outside the checkout; reject accidental source-tree module imports."""
import importlib.util,json,pathlib,sys,tempfile
from evalforge.audit import audit_compare
root=pathlib.Path(sys.argv[1]).resolve();fixture=root/'docs/audit.json'
for name in ['evalforge','evalforge.__main__','evalforge.core','evalforge.cli','evalforge.runner','evalforge.scorers','evalforge.compare','evalforge.report','evalforge.audit']:
 p=pathlib.Path(importlib.util.find_spec(name).origin).resolve();assert root not in p.parents,(name,p);assert 'site-packages' in p.parts,(name,p);print(name,p)
for c in json.loads(fixture.read_text())['cases']:assert audit_compare(c['report']['spec'])==c['report']
print('Installed: nine module origins and all 24 complete reports pass')
