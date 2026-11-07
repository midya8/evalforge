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
  --fail-under 1.0
python3 - <<'PY'
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
PY
printf '%s\n' 'Open .evalforge-demo/report.html in a browser. CI can consume .evalforge-demo/results.xml and .evalforge-demo/summary.md.'
