"""Run the full existing suite and retained reports against an isolated wheel.

Copied tests and evidence contain no evalforge package source. These are
same-runtime packaging checks, not independent statistical evidence.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]
MODULES = ['evalforge', 'evalforge.__main__', 'evalforge.core', 'evalforge.cli',
           'evalforge.runner', 'evalforge.scorers', 'evalforge.compare',
           'evalforge.report', 'evalforge.audit', 'evalforge.family',
           'evalforge.family_cli']
ENV = os.environ.copy()
ENV.pop('PYTHONPATH', None)


def call(command, cwd, text=None):
    return subprocess.check_output(command, cwd=cwd, env=ENV, input=text, text=True)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--section', choices=['all', 'tests', 'reports'], default='all')
args = parser.parse_args()
with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    wheels = work / 'wheels'
    wheels.mkdir()
    call([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '-w', str(wheels), str(ROOT)], work)
    built = list(wheels.glob('*.whl'))
    assert len(built) == 1, built
    venv.create(work / 'env', with_pip=True)
    py = str(work / 'env/bin/python')
    call([py, '-m', 'pip', 'install', '--no-deps', str(built[0])], work)
    outside = work / 'outside'
    outside.mkdir()
    for name in ['tests', 'examples', 'docs']:
        shutil.copytree(ROOT / name, outside / name)
    assert not (outside / 'evalforge').exists()
    suite = '''
import importlib,importlib.util,json,pathlib,sys,unittest
outside=pathlib.Path.cwd().resolve()
sys.path.insert(0,str(outside))
source=pathlib.Path(sys.argv[1]).resolve()
prefix=pathlib.Path(sys.prefix).resolve()
names=json.loads(sys.argv[2])
for name in names:
    if name!='evalforge.__main__':importlib.import_module(name)
def check():
    for name in names:
        origin=pathlib.Path(importlib.util.find_spec(name).origin).resolve()
        assert origin.is_relative_to(prefix),(name,origin)
        assert not origin.is_relative_to(source),(name,origin)
        assert 'site-packages' in origin.parts,(name,origin)
check()
if sys.argv[3]=='tests':
    tests=unittest.defaultTestLoader.discover(str(outside/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(tests)
    assert result.testsRun>0 and result.wasSuccessful()
    print(json.dumps(dict(tests=result.testsRun)))
check()
print(json.dumps(dict(installed_origins=len(names),checked_before_and_after=True)))
'''
    def origins(mode):
        print(call([py, '-I', '-c', suite, str(ROOT), json.dumps(MODULES), mode], outside))

    if args.section in ['all', 'tests']:
        origins('tests')
    if args.section in ['all', 'reports']:
        origins('origins')
        api = '''
import json,pathlib
from evalforge.audit import audit_compare
from evalforge import family_report
p=pathlib.Path.cwd()
for case in json.loads((p/'docs/audit.json').read_text())['cases']:
    assert audit_compare(case['report']['spec'])==case['report']
for case in json.loads((p/'examples/family-reports.json').read_text()):
    assert family_report(case['report']['input'])==case['report']
print('48 complete installed API reports match retained evidence')
'''
        print(call([py, '-I', '-c', api], outside))
        count = 0
        for case in json.loads((outside / 'docs/audit.json').read_text())['cases']:
            report = case['report']
            spec = outside / 'spec.json'
            spec.write_text(json.dumps(report['spec']))
            for entry in [[py, '-I', '-m', 'evalforge'], [str(Path(py).with_name('evalforge'))]]:
                output = outside / 'audit-output.json'
                if output.exists():
                    output.unlink()
                call(entry + ['audit', '--spec', str(spec), '--json', str(output)], outside)
                assert json.loads(output.read_text()) == report
                count += 1
        for case in json.loads((outside / 'examples/family-reports.json').read_text()):
            report = case['report']
            for entry in [[py, '-I', '-m', 'evalforge.family_cli'],
                          [str(Path(py).with_name('evalforge-family'))]]:
                output = call(entry + ['--input', '-'], outside, json.dumps(report['input']))
                assert json.loads(output) == report
                count += 1
        origins('origins')
        print(json.dumps(dict(complete_api_reports=48, complete_cli_reports=count,
                              entrypoints=4, retained_report_kinds=2)))
