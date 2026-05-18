#!/usr/bin/env python3
"""test-check-no-main-edits-protected-set.py — Inv 31.

check-no-main-edits.py MUST protect exactly {main, master} (matching
rabbit-cage Inv 21). It MUST NOT forbid additional branches (trunk, develop).
"""

import os
import sys
import re

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-no-main-edits.py")

FAIL = 0

with open(SCRIPT) as f:
    src = f.read()

# t1: trunk and develop MUST NOT appear as protected branches
for extra in ("trunk", "develop"):
    if extra in src:
        print(f"FAIL t1: '{extra}' still listed as a protected branch", file=sys.stderr)
        FAIL = 1
    else:
        print(f"PASS t1: '{extra}' not protected")

# t2: main and master must still be protected
if '"main"' not in src and "'main'" not in src:
    print("FAIL t2: 'main' not protected", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t2: 'main' protected")

if '"master"' not in src and "'master'" not in src:
    print("FAIL t2: 'master' not protected", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t2: 'master' protected")

if FAIL:
    print("test-check-no-main-edits-protected-set: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-check-no-main-edits-protected-set: all checks passed.")
