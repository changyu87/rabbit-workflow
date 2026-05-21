#!/usr/bin/env python3
"""test-check-naming-bans-rbt.py — BUG-3 / Inv 15

End-to-end test that check-naming.py bans the 'rbt-' prefix (rabbit-cage Inv 10)
and no longer treats 'rwf-' as banned (rwf- was never a banned prefix in this
repo).

t1: a fixture .claude/ tree containing a file under .claude/agents/ with an
    'rbt-' prefix triggers a violation (exit 1, stderr mentions rbt-).
t2: a fixture .claude/ tree containing a file under .claude/agents/ named
    'rwf-thing.md' (rwf- prefix) does NOT trigger a violation due to rwf-
    (it may still fail rabbit- prefix check, but stderr must not mention rwf-).
t3: check-naming.py source contains no 'rwf-' literal.
t4: check-naming.py source contains the 'rbt-' literal as a banned prefix.
"""

import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-naming.py")

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS t{n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: rbt- prefixed file triggers violation
with tempfile.TemporaryDirectory() as tmp:
    agents_dir = os.path.join(tmp, ".claude", "agents")
    os.makedirs(agents_dir)
    with open(os.path.join(agents_dir, "rbt-bad-agent.md"), "w") as f:
        f.write("---\nname: rbt-bad-agent\n---\n")
    r1 = subprocess.run(["python3", SCRIPT, tmp], capture_output=True, text=True)
    if r1.returncode == 1 and "rbt-" in r1.stderr:
        ok(1, "rbt- prefix triggers violation with stderr mentioning rbt-")
    else:
        fail_t(1, f"expected exit 1 + 'rbt-' in stderr; got rc={r1.returncode}, stderr={r1.stderr!r}")

# t2: rwf- prefix is NOT in banned prefix list. We place an rwf- file outside
# .claude/{commands,agents,skills} so the 'must start with rabbit-' rule does
# not apply; only a banned-prefix scan would flag it. Expect exit 0 (no violation).
with tempfile.TemporaryDirectory() as tmp:
    hooks_dir = os.path.join(tmp, ".claude", "hooks")
    os.makedirs(hooks_dir)
    with open(os.path.join(hooks_dir, "rwf-legacy.sh"), "w") as f:
        f.write("#!/bin/bash\n")
    r2 = subprocess.run(["python3", SCRIPT, tmp], capture_output=True, text=True)
    if r2.returncode == 0:
        ok(2, "rwf- prefix is not flagged as banned (rwf- is no longer in BANNED_PREFIXES)")
    else:
        fail_t(2, f"check-naming.py still flags rwf- as banned; rc={r2.returncode}, stderr={r2.stderr!r}")

# t3: script source contains no 'rwf-' literal
with open(SCRIPT) as f:
    src = f.read()
if "rwf-" not in src:
    ok(3, "check-naming.py source contains no 'rwf-' literal")
else:
    fail_t(3, "check-naming.py still references 'rwf-'")

# t4: script source contains 'rbt-' literal (as banned prefix)
if "rbt-" in src:
    ok(4, "check-naming.py contains 'rbt-' as banned prefix")
else:
    fail_t(4, "check-naming.py does not contain 'rbt-' banned prefix literal")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
