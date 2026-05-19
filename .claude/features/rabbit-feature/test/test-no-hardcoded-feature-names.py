#!/usr/bin/env python3
# test-no-hardcoded-feature-names.py — Inv 10 / BUG-21
#
# The assembled prompt's RULES section MUST NOT hardcode specific feature
# names. The dynamically-populated REGISTERED FEATURES block may legitimately
# contain feature names; this test isolates the RULES section and asserts no
# specific feature literals appear there.

import re
import subprocess
import sys
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
script = Path(repo_root) / ".claude/features/rabbit-feature-scope/scripts/resolve-scope.py"

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1

def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1

result = subprocess.run(
    [sys.executable, str(script), "test hardcoded feature names"],
    capture_output=True, text=True
)
prompt = result.stdout

# Isolate the RULES section: from "Rules:" (or similar) to end of prompt.
m = re.search(r"(?im)^\s*rules\s*:\s*$", prompt)
if not m:
    fail("Inv 10: could not locate 'Rules:' section in prompt")
else:
    rules_block = prompt[m.end():]
    # Forbidden hardcoded literals — names from the original BUG-21 instance.
    forbidden = ["contract", "rabbit-cage"]
    found = [n for n in forbidden if n in rules_block]
    if not found:
        ok("Inv 10: RULES section contains no hardcoded feature names")
    else:
        fail(f"Inv 10: RULES section hardcodes feature name(s): {found}")

# Also assert that quoted feature names like '"contract"' or '"rabbit-cage"'
# don't appear in the RULES section (covers the original phrasing exactly).
if m:
    rules_block = prompt[m.end():]
    bad_quoted = [q for q in ['"contract"', '"rabbit-cage"'] if q in rules_block]
    if not bad_quoted:
        ok("Inv 10: RULES section contains no quoted hardcoded feature names")
    else:
        fail(f"Inv 10: RULES section has quoted feature name(s): {bad_quoted}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
