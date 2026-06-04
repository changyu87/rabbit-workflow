#!/usr/bin/env python3
"""test-template-schema-producer-live-refs.py — Inv 16.

check-template-schema-producer-consistency.py MUST not reference deleted
producers (file-bug.sh, relink.sh, etc.). End-to-end: invoke it on the real
bug-template.json and verify it succeeds without dead references.
"""

import os
import sys
import subprocess

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-template-schema-producer-consistency.py")
TEMPLATE = os.path.join(FEATURE_DIR, "templates/bug-template.json")

FAIL = 0

# t1: script source must not name deleted producers
with open(SCRIPT) as f:
    src = f.read()

dead = ["file-bug.sh", "relink.sh"]
for name in dead:
    if name in src:
        print(f"FAIL t1: script references deleted producer '{name}'", file=sys.stderr)
        FAIL = 1
    else:
        print(f"PASS t1: script does not reference '{name}'")

# t2 (end-to-end): script must successfully validate live bug-template.json
proc = subprocess.run(
    ["python3", SCRIPT, TEMPLATE],
    capture_output=True, text=True
)
if proc.returncode != 0:
    print(f"FAIL t2: script exited {proc.returncode} for live template", file=sys.stderr)
    print(f"  stdout: {proc.stdout}", file=sys.stderr)
    print(f"  stderr: {proc.stderr}", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t2: script succeeds on live bug-template.json")

if FAIL:
    print("test-template-schema-producer-live-refs: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-template-schema-producer-live-refs: all checks passed.")
