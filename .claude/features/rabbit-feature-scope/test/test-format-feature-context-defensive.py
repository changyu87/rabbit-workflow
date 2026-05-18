#!/usr/bin/env python3
# test-format-feature-context-defensive.py — Inv 11 / BUG-28
#
# format-feature-context.py MUST tolerate feature.json entries that lack
# optional keys (summary, version, tdd_state, deprecation_criterion). It
# MUST exit non-zero only when an entry is missing the required 'name' key
# (the JSON field that identifies the feature).

import json
import subprocess
import sys
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
script = Path(repo_root) / ".claude/features/rabbit-feature-scope/scripts/format-feature-context.py"

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


def run_with(input_obj):
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(input_obj),
        capture_output=True, text=True,
    )


# Case 1: entry missing optional 'summary' — must not crash.
res = run_with([{"name": "feat-a", "path": ".claude/features/feat-a"}])
if res.returncode == 0 and "feat-a" in res.stdout:
    ok("Inv 11: missing 'summary' key tolerated")
else:
    fail(f"Inv 11: missing 'summary' crashed; rc={res.returncode}, stderr={res.stderr!r}")

# Case 2: entry with only the required identifying key — must not crash.
res = run_with([{"name": "feat-b"}])
if res.returncode == 0 and "feat-b" in res.stdout:
    ok("Inv 11: entry with only 'name' tolerated")
else:
    fail(f"Inv 11: minimal entry crashed; rc={res.returncode}, stderr={res.stderr!r}")

# Case 3: empty array — must succeed.
res = run_with([])
if res.returncode == 0:
    ok("Inv 11: empty array tolerated")
else:
    fail(f"Inv 11: empty array crashed; rc={res.returncode}")

# Case 4: entry missing required 'name' key — must exit non-zero with stderr.
res = run_with([{"path": "x", "summary": "y"}])
if res.returncode != 0 and res.stderr.strip():
    ok("Inv 11: missing required 'name' key fails non-zero with stderr")
else:
    fail(f"Inv 11: should fail on missing 'name'; rc={res.returncode}, stderr={res.stderr!r}")

# Case 5: malformed JSON on stdin — must exit non-zero.
res = subprocess.run(
    [sys.executable, str(script)],
    input="not json",
    capture_output=True, text=True,
)
if res.returncode != 0:
    ok("Inv 11: malformed JSON fails non-zero")
else:
    fail("Inv 11: malformed JSON should fail non-zero")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
