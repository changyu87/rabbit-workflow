#!/usr/bin/env python3
# test-check-naming-no-rbt.py — assert that check-naming.py contains no reference to
# 'rbt-' in any comment or flag message.
#
# Non-interactive. Exits non-zero on failure.

import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-naming.py")
PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: the script exists (sanity check)
if os.path.isfile(SCRIPT):
    ok("t1", "check-naming.py exists")
else:
    fail("t1", f"check-naming.py missing at {SCRIPT}")

# t2: no occurrence of 'rbt-' in the file (comments, flag messages, or any line)
if os.path.isfile(SCRIPT):
    content = open(SCRIPT).read()
    if "rbt-" in content:
        fail("t2", "check-naming.py contains 'rbt-' reference (deprecated prefix must be removed from all comments and flag messages)")
    else:
        ok("t2", "check-naming.py contains no 'rbt-' reference")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-check-naming-no-rbt: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-check-naming-no-rbt: all checks passed.")
