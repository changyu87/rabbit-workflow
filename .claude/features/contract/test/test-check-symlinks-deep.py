#!/usr/bin/env python3
"""test-check-symlinks-deep.py — Inv 21.

check-symlinks-resolve.py MUST follow symlinks at any depth (no maxdepth
limit). End-to-end: a dangling symlink nested 5 levels deep MUST be found.
"""

import os
import sys
import subprocess
import tempfile
import shutil

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-symlinks-resolve.py")

FAIL = 0

# t1: source must not hardcode a maxdepth-3 limit
with open(SCRIPT) as f:
    src = f.read()

if "depth >= 3" in src or "maxdepth=3" in src or "maxdepth 3" in src:
    print("FAIL t1: script still hardcodes maxdepth=3", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: script does not hardcode maxdepth=3")

# t2 (end-to-end): create a deep nesting with a dangling symlink at 5 levels
TMPDIR = tempfile.mkdtemp()
try:
    deep = os.path.join(TMPDIR, ".claude", "a", "b", "c", "d")
    os.makedirs(deep, exist_ok=True)
    link = os.path.join(deep, "dangler")
    os.symlink("/no/such/target/abc123", link)

    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR],
        capture_output=True, text=True
    )
    out = proc.stdout + proc.stderr
    if proc.returncode == 0:
        print("FAIL t2: deep dangling symlink not detected (exit 0)", file=sys.stderr)
        print(f"  output: {out}", file=sys.stderr)
        FAIL = 1
    elif "DANGLING" not in out:
        print("FAIL t2: no DANGLING line in output", file=sys.stderr)
        print(f"  output: {out}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t2: deep dangling symlink detected")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

if FAIL:
    print("test-check-symlinks-deep: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-check-symlinks-deep: all checks passed.")
