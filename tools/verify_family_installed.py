"""Independent installed-module and CLI evidence from outside the checkout."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from evalforge import family_report
root=Path(sys.argv[1]).resolve()
for name in ['evalforge','evalforge.family','evalforge.family_cli']:
 p=Path(importlib.util.find_spec(name).origin).resolve()
 assert root not in p.parents and 'site-packages' in p.parts,(name,p)
 print(name,p)
for c in json.loads((root/'examples/family-reports.json').read_text()):
 r=c['report'];assert family_report(r['input'])==r
 for executable in [[sys.executable,'-I','-m','evalforge.family_cli'],[str(Path(sys.executable).with_name('evalforge-family'))]]:
  p=subprocess.run(executable+['--input','-'],input=json.dumps(r['input']),text=True,capture_output=True)
  assert p.returncode==0,p.stderr
  assert json.loads(p.stdout)==r
print('Installed separate API, module and console entry: all 24 reports each exact')
