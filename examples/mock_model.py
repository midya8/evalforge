#!/usr/bin/env python3
"""Deterministic local adapter used by the demo and tests.

It is intentionally not a model. It proves the evaluation loop without paid APIs,
network calls, or hidden credentials; point --cmd at any real adapter to evaluate it.
"""

import json
import sys

prompt = sys.stdin.read()
lower = prompt.lower()

if "json" in lower and "toronto" in lower:
    print(json.dumps({"city": "Toronto", "units": "metric", "answer": "Toronto, Canada"}))
elif "incident" in lower:
    print("INCIDENT SUMMARY: checkout latency rose after deploy 2026-11-06T22:10Z; rollback restored p95 under 500 ms.")
elif "calculate" in lower:
    print("The result is 42.")
elif "summarize" in lower:
    print("Evaluate agents with versioned tasks, deterministic checks, regression gates, and readable reports.")
elif "classify" in lower:
    print("billing")
else:
    print("Use explicit acceptance checks, keep raw outputs, and compare every candidate against a baseline.")
