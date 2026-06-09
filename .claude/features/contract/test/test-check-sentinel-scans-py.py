#!/usr/bin/env python3
"""test-check-sentinel-scans-py.py — Inv 17.

check-sentinel.py MUST scan .py files (Python-only stack). End-to-end: on a
directory with a .py file lacking the sentinel, the script must fail.
"""

import os
import sys
import subprocess
import tempfile
import shutil

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-sentinel.py")

FAIL = 0

# t1: source must NOT scan .sh-only walk; must include .py
with open(SCRIPT) as f:
    src = f.read()

if '.py' not in src:
    print("FAIL t1: script source does not mention .py", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: script source mentions .py")

# t1b: script must NOT walk .sh files (Python-only stack per Inv 5)
if '.sh' in src:
    print("FAIL t1b: script still references .sh (Python-only stack per Inv 5)", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1b: script does not reference .sh")

# t2 (end-to-end): a DISPATCH .py file (wraps build-prompt) without the
# sentinel under the target dir must trigger failure. Inv 17 scope is
# dispatch/agent-prompt scripts only (#1132), so the fixture is a dispatch
# script — a plain .py is intentionally out of scope and would NOT fail.
TMPDIR = tempfile.mkdtemp()
try:
    py_path = os.path.join(TMPDIR, "dispatch_no_sentinel.py")
    with open(py_path, "w") as f:
        f.write("#!/usr/bin/env python3\n"
                'BUILD_PROMPT = "../contract/scripts/build-prompt.py"\n'
                "print('hello')\n")

    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR],
        capture_output=True, text=True
    )
    if proc.returncode == 0:
        print("FAIL t2: script returned 0 despite dispatch .py lacking sentinel", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t2: script flags dispatch .py file missing sentinel")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

# t3 (end-to-end): a DISPATCH .py file WITH the sentinel must pass.
TMPDIR2 = tempfile.mkdtemp()
try:
    py_path = os.path.join(TMPDIR2, "dispatch_with_sentinel.py")
    with open(py_path, "w") as f:
        f.write("#!/usr/bin/env python3\n# RABBIT-POLICY-BLOCK-v1\n"
                'BUILD_PROMPT = "../contract/scripts/build-prompt.py"\n'
                "print('hello')\n")

    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR2],
        capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(f"FAIL t3: script returned {proc.returncode} for .py file with sentinel", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t3: script passes on .py file with sentinel")
finally:
    shutil.rmtree(TMPDIR2, ignore_errors=True)

if FAIL:
    print("test-check-sentinel-scans-py: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-check-sentinel-scans-py: all checks passed.")
