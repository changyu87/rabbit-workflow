#!/usr/bin/env python3
"""Inv 22 — dual HANDOFF emission (YAML block followed by JSON block with
handoff_schema_version and required fields)."""
import json
import re

from _helpers import run_dispatch, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


res = run_dispatch()
if res.returncode != 0:
    print(f"FATAL: dispatch failed rc={res.returncode}: {res.stderr}")
    raise SystemExit(1)
prompt = res.stdout

# The "blocked HANDOFF:" schema inside the SCOPE BOUNDARY section is a
# separate construct (Inv 10). Inv 22 governs the FINAL completion HANDOFF,
# which lives under the "HANDOFF (emit on completion)" banner.
final_section_pos = prompt.find("HANDOFF (emit on completion)")
if final_section_pos < 0:
    ko("inv22: 'HANDOFF (emit on completion)' banner not found")
    final_section_pos = 0
yaml_pos = prompt.find("HANDOFF:\n", final_section_pos)
json_pos = prompt.find("HANDOFF_JSON:", final_section_pos)
if yaml_pos >= 0 and json_pos > yaml_pos:
    ok("inv22: final YAML HANDOFF appears before HANDOFF_JSON")
else:
    ko(f"inv22: final HANDOFF order wrong (yaml={yaml_pos}, json={json_pos})")

m = re.search(r"HANDOFF_JSON:\n```json\n(\{.*?\})\n```", prompt, re.DOTALL)
if not m:
    ko("inv22: HANDOFF_JSON fenced JSON block not found")
else:
    raw = m.group(1)
    # The block has template placeholders — verify required keys are present
    # before substitution; we don't need to json.loads it.
    required = {
        "handoff_schema_version",
        "feature",
        "tdd_state",
        "test_result",
        "spec_compliance",
        "tdd_report_path",
        "closed_items",
        "notes",
    }
    missing = [k for k in required if f'"{k}"' not in raw]
    if not missing:
        ok("inv22: HANDOFF_JSON has all required fields")
    else:
        ko(f"inv22: HANDOFF_JSON missing fields: {missing}")
    if '"handoff_schema_version": "1.1.0"' in raw:
        ok("inv22: HANDOFF_JSON declares handoff_schema_version 1.1.0")
    else:
        ko("inv22: HANDOFF_JSON missing handoff_schema_version 1.1.0")

report(passed, failed)
