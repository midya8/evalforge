# evalforge

A small harness for checking LLM or agent outputs against a task file, then comparing two runs to see what got worse. I wanted something I could run locally in CI without signing up for anything, so it's plain Python and shells out to whatever command produces your model's answer.

Each task is a line of JSONL with a prompt and either an expected answer or a list of checks (contains, regex, JSON subset, token F1, numeric tolerance, length). Your adapter gets the prompt on stdin and prints its answer.

```bash
python -m evalforge validate examples/tasks.jsonl
python -m evalforge run --tasks examples/tasks.jsonl \
  --cmd "python examples/mock_model.py" --out run.json --report report.html
python -m evalforge compare baseline.json run.json --max-drop .05
```

`run` can also write JUnit, Markdown and SARIF if you want it in a CI dashboard. `compare` fails when the mean score drops more than `--max-drop`, a passing task starts failing, or a baseline task goes missing. Exit codes are 0 pass, 1 gate failed, 2 bad input.

The bundled example is a six-task mock adapter (not a real model), and it comes out 6/6 with a mean score of 1.0.

There's also a browser page for poking at two result lists side by side, with a paired sign-flip test and McNemar's test on the pass/fail changes: https://midya8.github.io/evalforge/. A second page (`family.html`, plus `python -m evalforge.family_cli --input examples/family.json`) handles the case where several candidates share clustered tasks. FAMILY.md has the details on that one.

Note that adapter commands run with your permissions, nothing is sandboxed.

Tests:

```bash
python -m unittest discover -s tests
```

108 Python tests at the moment, plus a few Node/Chrome tests for the browser pages (`npm test`).
