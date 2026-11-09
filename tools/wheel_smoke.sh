#!/bin/sh
set -eu
ROOT=$(pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
python -m venv "$TMP/env"
"$TMP/env/bin/pip" -q wheel --no-deps --wheel-dir "$TMP/wheels" "$ROOT"
"$TMP/env/bin/pip" -q install --no-deps "$TMP"/wheels/*.whl
(cd "$TMP" && PYTHONPATH= "$TMP/env/bin/python" "$ROOT/tools/verify_installed.py" "$ROOT")
(cd "$TMP" && PYTHONPATH= "$TMP/env/bin/python" -m evalforge audit --spec "$ROOT/examples/audit.json" --json "$TMP/audit.json")
(cd "$TMP" && PYTHONPATH= "$TMP/env/bin/python" -m evalforge run --tasks "$ROOT/examples/tasks.jsonl" --cmd "$TMP/env/bin/python $ROOT/examples/mock_model.py" --out "$TMP/run.json" --report "$TMP/report.html" --junit "$TMP/results.xml" --markdown "$TMP/summary.md" --sarif "$TMP/run.sarif" --fail-under 1)
(cd "$TMP" && PYTHONPATH= "$TMP/env/bin/python" -m evalforge compare "$TMP/run.json" "$TMP/run.json" --format json --markdown "$TMP/compare.md" --sarif "$TMP/compare.sarif" > "$TMP/compare.json")
"$TMP/env/bin/python" -I - "$TMP" "$ROOT" <<'PY'
import json,pathlib,sys,xml.etree.ElementTree as ET
p=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2]);c=json.loads((p/'compare.json').read_text());assert c['ok'] and c['paired_summary']['count']==6 and c['paired_summary']['mean_score_delta']==0
from evalforge.audit import audit_compare
assert json.loads((p/'audit.json').read_text())==audit_compare(json.loads((root/'examples/audit.json').read_text()))
assert ET.parse(p/'results.xml').getroot().attrib['failures']=='0'
assert json.loads((p/'run.sarif').read_text())['runs'][0]['results']==[]
assert json.loads((p/'compare.sarif').read_text())['runs'][0]['results']==[]
print('Installed audit/adapter/compare CLI, HTML/JUnit/Markdown/SARIF pass')
PY
