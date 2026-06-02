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

# Inv 55 — discovered_issues and aborted_reason additive fields.
# (a) presence-and-default assertions on EVERY HANDOFF_JSON block in the
#     template. The dispatcher's assembled prompt embeds three such blocks:
#     STEP 5 fail-HANDOFF, STEP 7 fail-HANDOFF, completion HANDOFF.
#     The fail-HANDOFF blocks live inside indented step bodies; use a
#     leading-whitespace-tolerant pattern and a brace-balanced extractor.
all_blocks = re.findall(
    r"HANDOFF_JSON:\n[ \t]*```json\n(.*?)\n[ \t]*```",
    prompt,
    re.DOTALL,
)
if len(all_blocks) != 3:
    ko(f"inv55: expected 3 HANDOFF_JSON blocks in template, found {len(all_blocks)}")
else:
    ok("inv55: found 3 HANDOFF_JSON blocks (STEP 5 fail, STEP 7 fail, completion)")

for i, block in enumerate(all_blocks):
    label = ["STEP-5-fail", "STEP-7-fail", "completion"][i] if i < 3 else f"block-{i}"
    if '"discovered_issues": []' in block:
        ok(f"inv55: {label} HANDOFF_JSON has discovered_issues: [] default")
    else:
        ko(f"inv55: {label} HANDOFF_JSON missing literal 'discovered_issues': []")
    if '"aborted_reason": null' in block:
        ok(f"inv55: {label} HANDOFF_JSON has aborted_reason: null default")
    else:
        ko(f"inv55: {label} HANDOFF_JSON missing literal 'aborted_reason': null")

# (b) populated-case parse test — a synthetic HANDOFF JSON with both fields
#     populated parses as valid JSON and conforms to Inv 55 typing.
synthetic = {
    "handoff_schema_version": "1.1.0",
    "feature": "x",
    "tdd_state": "test-green",
    "test_result": "pass",
    "spec_compliance": "pass",
    "tdd_report_path": None,
    "closed_items": [],
    "notes": "...",
    "discovered_issues": [{"title": "x", "body": "y", "labels": ["z"]}],
    "aborted_reason": "blocked-by-#999",
}
try:
    parsed = json.loads(json.dumps(synthetic))
    di = parsed["discovered_issues"]
    ar = parsed["aborted_reason"]
    typing_ok = (
        isinstance(di, list)
        and all(
            isinstance(e, dict)
            and isinstance(e.get("title"), str)
            and isinstance(e.get("body"), str)
            and isinstance(e.get("labels"), list)
            and all(isinstance(l, str) for l in e["labels"])
            for e in di
        )
        and isinstance(ar, str)
        and len(ar) > 0
    )
    if typing_ok:
        ok("inv55: populated synthetic HANDOFF conforms to Inv 55 typing")
    else:
        ko("inv55: populated synthetic HANDOFF failed Inv 55 typing check")
except Exception as e:
    ko(f"inv55: synthetic HANDOFF parse failed: {e}")

# (c) negative test — a discovered_issues element missing a required key
#     does NOT conform to the invariant's typing.
bad = {
    "discovered_issues": [{"title": "x", "body": "y"}],  # missing labels
}
elem = bad["discovered_issues"][0]
required_keys = {"title", "body", "labels"}
missing_keys = required_keys - set(elem.keys())
if missing_keys:
    ok(f"inv55: negative case rejected — element missing keys: {sorted(missing_keys)}")
else:
    ko("inv55: negative case incorrectly considered conforming")

report(passed, failed)
