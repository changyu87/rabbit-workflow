#!/usr/bin/env python3
# test-validate-no-bugs-root.py — verify validate-feature.py handles absence of bugs_root.
#
# t1: exits 0 for a valid feature.json with NO bugs_root field
# t2: exits non-zero for a feature.json missing owner (other required field)

import os
import sys
import subprocess
import tempfile
import shutil
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VALIDATE = os.path.join(FEATURE_DIR, "scripts/validate-feature.py")
FAIL = 0


def make_fixture():
    """Build a minimal valid feature dir without bugs_root."""
    d = tempfile.mkdtemp()
    name = os.path.basename(d)

    os.makedirs(os.path.join(d, "specs"), exist_ok=True)
    os.makedirs(os.path.join(d, "docs/bugs"), exist_ok=True)
    os.makedirs(os.path.join(d, "test"), exist_ok=True)

    with open(os.path.join(d, "specs/spec.md"), "w") as f:
        f.write("# Minimal spec\nContent for test fixture.\n")

    with open(os.path.join(d, "specs/contract.md"), "w") as f:
        f.write("# Minimal contract\nContent for test fixture.\n")

    # test/run.py must exist and be executable (validate-feature.py checks for run.py per Inv 14)
    run_py = os.path.join(d, "test/run.py")
    with open(run_py, "w") as f:
        f.write('#!/usr/bin/env python3\nimport sys; sys.exit(0)\n')
    os.chmod(run_py, 0o755)

    feature_data = {
        "name": name,
        "version": "0.1.0",
        "owner": "test-owner",
        "tdd_state": "spec",
        "summary": "Fixture for test-validate-no-bugs-root.",
        "surface": {
            "hooks": [],
            "commands": [],
            "agents": [],
            "skills": []
        },
        "deprecation_criterion": "when test is done"
    }
    with open(os.path.join(d, "feature.json"), "w") as f:
        json.dump(feature_data, f, indent=2)

    return d


# ---------------------------------------------------------------------------
# t1: valid feature.json lacking bugs_root — must exit 0
# ---------------------------------------------------------------------------
FIXTURE1 = make_fixture()

proc1 = subprocess.run(
    ["python3", VALIDATE, FIXTURE1],
    capture_output=True, text=True
)
OUTPUT1 = proc1.stdout + proc1.stderr
EXIT1 = proc1.returncode

shutil.rmtree(FIXTURE1, ignore_errors=True)

if EXIT1 != 0:
    print(f"FAIL t1: validate-feature.py exited {EXIT1} for feature.json without bugs_root (expected 0)", file=sys.stderr)
    print(f"  output: {OUTPUT1}", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: validate-feature.py exits 0 when bugs_root is absent")

# ---------------------------------------------------------------------------
# t2: feature.json missing 'owner' — must exit non-zero
# ---------------------------------------------------------------------------
FIXTURE2 = tempfile.mkdtemp()
os.makedirs(os.path.join(FIXTURE2, "specs"), exist_ok=True)
os.makedirs(os.path.join(FIXTURE2, "docs/bugs"), exist_ok=True)
os.makedirs(os.path.join(FIXTURE2, "test"), exist_ok=True)

with open(os.path.join(FIXTURE2, "specs/spec.md"), "w") as f:
    f.write("# Minimal spec\nContent.\n")
with open(os.path.join(FIXTURE2, "specs/contract.md"), "w") as f:
    f.write("# Minimal contract\nContent.\n")

run_py2 = os.path.join(FIXTURE2, "test/run.py")
with open(run_py2, "w") as f:
    f.write('#!/usr/bin/env python3\nimport sys; sys.exit(0)\n')
os.chmod(run_py2, 0o755)

FIXTURE2_NAME = os.path.basename(FIXTURE2)
feature_data2 = {
    "name": FIXTURE2_NAME,
    "version": "0.1.0",
    "tdd_state": "spec",
    "summary": "Fixture missing owner for t2.",
    "surface": {
        "hooks": [],
        "commands": [],
        "agents": [],
        "skills": []
    },
    "deprecation_criterion": "when test is done"
}
with open(os.path.join(FIXTURE2, "feature.json"), "w") as f:
    json.dump(feature_data2, f, indent=2)

proc2 = subprocess.run(
    ["python3", VALIDATE, FIXTURE2],
    capture_output=True, text=True
)
OUTPUT2 = proc2.stdout + proc2.stderr
EXIT2 = proc2.returncode

shutil.rmtree(FIXTURE2, ignore_errors=True)

if EXIT2 == 0:
    print("FAIL t2: validate-feature.py exited 0 for feature.json missing owner (expected non-zero)", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t2: validate-feature.py exits non-zero when owner is missing")

# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------
if FAIL != 0:
    print("test-validate-no-bugs-root: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-validate-no-bugs-root: all checks passed.")
