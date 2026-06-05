#!/usr/bin/env python3
"""test-validate-feature-sweep.py — contract spec Inv 63.

End-to-end coverage for validate-feature.py's ADDITIVE aggregate sweep mode
(`all` / multiple feature-dir paths), which absorbs the cross-feature audit
sweep formerly provided by the rabbit-feature-audit skill.

t1: single-feature mode is unchanged — a valid fixture passes (exit 0).
t2: `validate-feature.py all` validates every real feature dir and exits 0
    on a green repo, emitting per-feature PASS lines and a SUMMARY line.
t3: a sweep containing one failing fixture dir reports that dir as FAIL,
    emits the SUMMARY line, and exits 1.
t4: per-feature line shape (`<name>: PASS|FAIL`) and the SUMMARY line are
    present in `all` output, and contract (a real feature) is reported PASS.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/validate-feature.py")
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))

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


def make_valid_feature(parent, name):
    fdir = os.path.join(parent, name)
    os.makedirs(os.path.join(fdir, "specs"), exist_ok=True)
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
    run_py = os.path.join(fdir, "test", "run.py")
    with open(run_py, "w") as f:
        f.write("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n")
    os.chmod(run_py, os.stat(run_py).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return fdir


def make_broken_feature(parent, name):
    # Missing test/run.py -> validate_feature FAILS.
    fdir = os.path.join(parent, name)
    os.makedirs(os.path.join(fdir, "specs"), exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({
            "name": name,
            "version": "1.0.0",
            "owner": "test-owner",
            "tdd_state": "test-green",
            "summary": "broken fixture",
            "deprecation_criterion": "when test ends",
        }, f)
    with open(os.path.join(fdir, "specs", "spec.md"), "w") as f:
        f.write("spec\n")
    with open(os.path.join(fdir, "specs", "contract.md"), "w") as f:
        f.write("contract\n")
    return fdir


# t1: single-feature mode unchanged
with tempfile.TemporaryDirectory() as tmp:
    good = make_valid_feature(tmp, "feat_good")
    r1 = subprocess.run(["python3", SCRIPT, good], capture_output=True, text=True)
    if r1.returncode == 0:
        ok(1, "single-feature mode validates a good fixture (exit 0)")
    else:
        fail_t(1, f"expected exit 0, got {r1.returncode}; stderr={r1.stderr!r}")

# t2: `all` over the real repo exits 0 on a green repo
r2 = subprocess.run(
    ["python3", SCRIPT, "all"],
    capture_output=True, text=True,
    env={**os.environ, "RABBIT_ROOT": REPO_ROOT},
)
if r2.returncode == 0 and "SUMMARY:" in r2.stdout:
    ok(2, "`all` validates every real feature and exits 0 with a SUMMARY line")
else:
    fail_t(2, f"expected exit 0 + SUMMARY line; got rc={r2.returncode}, "
               f"stdout-tail={r2.stdout[-400:]!r}, stderr-tail={r2.stderr[-400:]!r}")

# t3: a sweep with a broken fixture dir reports FAIL + SUMMARY and exits 1
with tempfile.TemporaryDirectory() as tmp:
    good = make_valid_feature(tmp, "feat_good")
    bad = make_broken_feature(tmp, "feat_bad")
    r3 = subprocess.run(["python3", SCRIPT, good, bad], capture_output=True, text=True)
    combined = r3.stdout + r3.stderr
    has_fail_line = "feat_bad: FAIL" in combined
    has_summary = "SUMMARY:" in combined
    if r3.returncode == 1 and has_fail_line and has_summary:
        ok(3, "multi-dir sweep with one broken dir reports FAIL + SUMMARY and exits 1")
    else:
        fail_t(3, f"expected rc=1 + 'feat_bad: FAIL' + SUMMARY; got rc={r3.returncode}, "
                   f"fail_line={has_fail_line}, summary={has_summary}, "
                   f"stdout={r3.stdout[-400:]!r}, stderr={r3.stderr[-400:]!r}")

# t4: line shape in `all` output names a real feature as PASS
if "contract: PASS" in r2.stdout:
    ok(4, "`all` output reports the contract feature as 'contract: PASS'")
else:
    fail_t(4, f"expected 'contract: PASS' line in `all` output; stdout-tail={r2.stdout[-400:]!r}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
