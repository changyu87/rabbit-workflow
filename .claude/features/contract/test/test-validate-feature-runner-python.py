#!/usr/bin/env python3
"""test-validate-feature-runner-python.py — BUG-2 / Inv 11

End-to-end test that validate-feature.py checks for test/run.py (Python runner),
not test/run.sh (legacy shell runner).

t1: a fixture feature dir with test/run.py present and executable PASSES.
t2: a fixture feature dir with only test/run.sh (no run.py) FAILS with stderr
    mentioning run.py.
t3: validate-feature.py source contains no reference to "run.sh".
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/validate-feature.py")

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


def make_min_feature(root, name, with_run_py=False, with_run_sh=False):
    fdir = os.path.join(root, name)
    os.makedirs(os.path.join(fdir, "specs"), exist_ok=True)
    os.makedirs(os.path.join(fdir, "docs", "bugs"), exist_ok=True)
    os.makedirs(os.path.join(fdir, "test"), exist_ok=True)

    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({
            "name": name,
            "version": "1.0.0",
            "owner": "test-owner",
            "tdd_state": "test-green",
            "summary": "fixture",
            "surface": {"hooks": [], "commands": [], "agents": [], "skills": []},
            "deprecation_criterion": "when test ends",
        }, f)

    with open(os.path.join(fdir, "specs", "spec.md"), "w") as f:
        f.write("spec\n")
    with open(os.path.join(fdir, "specs", "contract.md"), "w") as f:
        f.write("contract\n")

    if with_run_py:
        run_py = os.path.join(fdir, "test", "run.py")
        with open(run_py, "w") as f:
            f.write("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n")
        os.chmod(run_py, os.stat(run_py).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if with_run_sh:
        run_sh = os.path.join(fdir, "test", "run.sh")
        with open(run_sh, "w") as f:
            f.write("#!/bin/bash\nexit 0\n")
        os.chmod(run_sh, os.stat(run_sh).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return fdir


with tempfile.TemporaryDirectory() as tmp:
    # t1: feature with run.py passes
    fdir1 = make_min_feature(tmp, "feat_with_runpy", with_run_py=True)
    r1 = subprocess.run(["python3", SCRIPT, fdir1], capture_output=True, text=True)
    if r1.returncode == 0:
        ok(1, "feature with test/run.py validates (exit 0)")
    else:
        fail_t(1, f"expected exit 0, got {r1.returncode}; stderr={r1.stderr!r}")

    # t2: feature with only run.sh fails, stderr mentions run.py
    fdir2 = make_min_feature(tmp, "feat_only_runsh", with_run_py=False, with_run_sh=True)
    r2 = subprocess.run(["python3", SCRIPT, fdir2], capture_output=True, text=True)
    if r2.returncode != 0 and "run.py" in r2.stderr:
        ok(2, "feature missing test/run.py fails and stderr names run.py")
    else:
        fail_t(2, f"expected non-zero exit and stderr containing 'run.py'; got rc={r2.returncode}, stderr={r2.stderr!r}")

# t3: script source contains no "run.sh" literal
with open(SCRIPT) as f:
    src = f.read()
if "run.sh" not in src:
    ok(3, "validate-feature.py source contains no 'run.sh' reference")
else:
    fail_t(3, "validate-feature.py still references 'run.sh'")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
