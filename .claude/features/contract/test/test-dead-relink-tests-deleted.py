#!/usr/bin/env python3
"""test-dead-relink-tests-deleted.py — BUG-35 / Inv 21

End-to-end test that dead test files referencing the deleted relink.sh have
been removed (not skipped, not commented out).

t1: test-relink-no-skills.py does not exist.
t2: test-relink.py does not exist (also references deleted relink.sh).
t3: no test-*.py file under test/ imports/references "scripts/relink.sh".
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

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


dead1 = os.path.join(TEST_DIR, "test-relink-no-skills.py")
if not os.path.exists(dead1):
    ok(1, "test-relink-no-skills.py has been deleted")
else:
    fail_t(1, f"dead test still exists at {dead1}")

dead2 = os.path.join(TEST_DIR, "test-relink.py")
if not os.path.exists(dead2):
    ok(2, "test-relink.py has been deleted")
else:
    fail_t(2, f"dead test still exists at {dead2}")

# t3: no remaining test file *invokes* scripts/relink.sh (legitimate
# absence-assertions like test-build-contract.py's t5 are allowed).
offenders = []
SELF = os.path.basename(__file__)
# test-build-contract.py asserts relink.sh ABSENCE per Inv 11 — that is allowed.
ALLOWED = {SELF, "test-build-contract.py"}
for fname in os.listdir(TEST_DIR):
    if not fname.startswith("test-") or not fname.endswith(".py"):
        continue
    if fname in ALLOWED:
        continue
    fpath = os.path.join(TEST_DIR, fname)
    try:
        with open(fpath) as f:
            content = f.read()
    except OSError:
        continue
    if "scripts/relink.sh" in content:
        offenders.append(fname)

if not offenders:
    ok(3, "no test file references scripts/relink.sh")
else:
    fail_t(3, f"tests still reference deleted scripts/relink.sh: {offenders}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
