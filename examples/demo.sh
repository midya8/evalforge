#!/bin/sh
set -eu
mkdir -p .evalforge-demo
python3 -m evalforge run \
  --tasks examples/tasks.jsonl \
  --cmd "python3 examples/mock_model.py" \
  --out .evalforge-demo/run.json \
  --report .evalforge-demo/report.html \
  --fail-under 1.0
printf '%s\n' 'Open .evalforge-demo/report.html in a browser.'
