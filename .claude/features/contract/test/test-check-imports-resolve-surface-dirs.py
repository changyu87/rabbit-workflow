#!/usr/bin/env python3
"""test-check-imports-resolve-surface-dirs.py — Inv 25.

check-imports-resolve.py import-target regex MUST cover all .claude surface
dirs: features/, hooks/, skills/, commands/, agents/. End-to-end: a doc
referencing a missing `.claude/hooks/foo.py` must be flagged.
"""

import os
import sys
import subprocess
import tempfile
import shutil

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/enforcement/check-imports-resolve.py")
LIB = os.path.join(FEATURE_DIR, "lib/checks.py")

FAIL = 0

# Per BACKLOG-26, check-imports-resolve.py is a thin shim around
# contract.lib.checks.check_imports_resolve; the surface-dir regex now lives
# in lib/checks.py.
with open(LIB) as f:
    src = f.read()

# t1: library source must reference all five surface dirs
for surface in ("features", "hooks", "skills", "commands", "agents"):
    if surface not in src:
        print(f"FAIL t1: library does not handle '{surface}/' imports", file=sys.stderr)
        FAIL = 1
    else:
        print(f"PASS t1: library source mentions '{surface}'")

# t2 (end-to-end): fixture feature with docs referencing missing .claude/hooks/x.py must fail
TMPDIR = tempfile.mkdtemp()
try:
    fdir = os.path.join(TMPDIR, "fake-feature")
    docs = os.path.join(fdir, "docs")
    os.makedirs(docs, exist_ok=True)
    with open(os.path.join(docs, "spec.md"), "w") as f:
        f.write("See `.claude/hooks/no-such-hook.py` for details.\n")

    # Init a fake git repo so the script can find a root
    subprocess.run(["git", "init", "-q", TMPDIR], capture_output=True)

    env = os.environ.copy()
    env["RABBIT_ROOT"] = TMPDIR

    proc = subprocess.run(
        ["python3", SCRIPT, fdir],
        capture_output=True, text=True, env=env,
    )
    out = proc.stdout + proc.stderr
    if proc.returncode == 0:
        print("FAIL t2: missing .claude/hooks/* import not detected (exit 0)", file=sys.stderr)
        print(f"  output: {out}", file=sys.stderr)
        FAIL = 1
    elif "MISSING" not in out:
        print("FAIL t2: no MISSING line in output", file=sys.stderr)
        print(f"  output: {out}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t2: missing .claude/hooks/* import detected")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

if FAIL:
    print("test-check-imports-resolve-surface-dirs: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-check-imports-resolve-surface-dirs: all checks passed.")
