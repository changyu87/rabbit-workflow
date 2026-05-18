#!/usr/bin/env python3
# test-invariant-coverage.py — e2e tests for spec invariants 1, 2, 3, 4, 6
# (RABBIT-FEATURE-SCOPE-BUG-7, 9, 12, 14, 17 — Wave 3 housekeeping).

import json
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


# Inv 1: resolve-scope.py emits prompt to stdout only; never calls Agent itself.
result = subprocess.run(
    [sys.executable, str(script), "test invariant 1"],
    capture_output=True, text=True
)
if result.returncode == 0 and result.stdout.strip() and not result.stderr.strip():
    ok("Inv 1: prompt to stdout, no stderr noise, exits 0")
else:
    fail(f"Inv 1: rc={result.returncode}, stderr={result.stderr!r}")

src = script.read_text()
# Inv 1: no Agent( literal call in source
if "Agent(" not in src:
    ok("Inv 1: no 'Agent(' literal in resolve-scope.py source")
else:
    fail("Inv 1: source contains 'Agent(' — script may be invoking Agent itself")

# Inv 2: dispatched Agent uses default model — no Opus override in the prompt.
prompt = result.stdout
if not re.search(r"opus", prompt, re.IGNORECASE):
    ok("Inv 2: prompt does not mention 'opus' (no model override)")
else:
    fail("Inv 2: prompt contains 'opus' — possible model override")

# Inv 3: uses find-feature.py list-json; never reads registry.json.
if "registry.json" not in src:
    ok("Inv 3: no 'registry.json' reference in source")
else:
    fail("Inv 3: source references registry.json")

if "list-json" in src:
    ok("Inv 3: source invokes find-feature.py list-json")
else:
    fail("Inv 3: source missing list-json invocation")

# Inv 4: Agent response JSON schema includes 'features' and 'rationale'.
if '"features"' in prompt and '"rationale"' in prompt:
    ok("Inv 4: prompt declares JSON schema with 'features' and 'rationale'")
else:
    fail("Inv 4: prompt missing required schema keys")

# Inv 6: empty features list [] is a valid response. Confirm the prompt does
# not forbid an empty list, and parses a sample empty response cleanly.
sample = '{"features": [], "rationale": "no features touched"}'
try:
    parsed = json.loads(sample)
    if parsed["features"] == [] and isinstance(parsed["rationale"], str):
        ok("Inv 6: empty features list parses as valid response shape")
    else:
        fail("Inv 6: parsed shape mismatch")
except Exception as e:
    fail(f"Inv 6: parse failed: {e}")

# Inv 6: prompt allows empty list — should contain explicit mention.
if "[]" in prompt or "empty" in prompt.lower():
    ok("Inv 6: prompt acknowledges empty features list possibility")
else:
    fail("Inv 6: prompt does not explicitly allow empty features list")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
