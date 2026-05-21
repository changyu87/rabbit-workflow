#!/usr/bin/env python3
"""test-check-naming-bans-rbt.py — BUG-3 / Inv 15

End-to-end test that check-naming.py bans the 'rbt-' prefix (rabbit-cage Inv 10).

t1: a fixture .claude/ tree containing a file under .claude/agents/ with an
    'rbt-' prefix triggers a violation (exit 1, stderr mentions rbt-).
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

# t4: script source contains 'rbt-' literal (as banned prefix)
with open(SCRIPT) as f:
    src = f.read()
if "rbt-" in src:
    ok(4, "check-naming.py contains 'rbt-' as banned prefix")
else:
    fail_t(4, "check-naming.py does not contain 'rbt-' banned prefix literal")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
