#!/bin/sh
set -eu
mkdir -p .evalforge-demo
python3 -m evalforge run \
  --tasks examples/tasks.jsonl \
  --cmd "python3 examples/mock_model.py" \
  --out .evalforge-demo/run.json \
  --report .evalforge-demo/report.html \
  --junit .evalforge-demo/results.xml \
  --markdown .evalforge-demo/summary.md \
  --sarif .evalforge-demo/analysis.sarif \
  --fail-under 1.0
cp .evalforge-demo/run.json .evalforge-demo/baseline.json
python3 -m evalforge compare \
  .evalforge-demo/baseline.json \
  .evalforge-demo/run.json \
  --markdown .evalforge-demo/comparison.md \
  --sarif .evalforge-demo/comparison.sarif
python3 - <<'PY'
import json
import xml.etree.ElementTree as ET
root = ET.parse('.evalforge-demo/results.xml').getroot()
assert root.attrib['tests'] == '6'
assert root.attrib['failures'] == '0'
assert len(root.findall('testcase')) == 6
summary = open('.evalforge-demo/summary.md', encoding='utf-8').read()
assert summary.startswith('# EvalForge evaluation\n')
assert '**Status:** PASS' in summary
assert '| Tasks | 6 |' in summary
assert '## Task results' in summary
comparison = open('.evalforge-demo/comparison.md', encoding='utf-8').read()
assert comparison.startswith('# EvalForge regression comparison\n')
assert '**Status:** PASS' in comparison
assert '| Common tasks | 6 |' in comparison
assert '| Regressions | 0 |' in comparison
analysis = json.load(open('.evalforge-demo/analysis.sarif', encoding='utf-8'))
assert analysis['version'] == '2.1.0'
assert analysis['$schema'] == 'https://json.schemastore.org/sarif-2.1.0.json'
analysis_run = analysis['runs'][0]
assert analysis_run['tool']['driver']['name'] == 'EvalForge'
assert analysis_run['results'] == []
assert analysis_run['invocations'][0]['executionSuccessful'] is True
comparison_sarif = json.load(open('.evalforge-demo/comparison.sarif', encoding='utf-8'))
assert comparison_sarif['version'] == '2.1.0'
comparison_run = comparison_sarif['runs'][0]
assert comparison_run['tool']['driver']['name'] == 'EvalForge'
assert comparison_run['results'] == []
assert comparison_run['invocations'][0]['executionSuccessful'] is True
PY
printf '%s\n' 'Open .evalforge-demo/report.html in a browser. CI can consume .evalforge-demo/results.xml, .evalforge-demo/summary.md, .evalforge-demo/comparison.md, .evalforge-demo/analysis.sarif and .evalforge-demo/comparison.sarif.'
