#!/usr/bin/env python3
# test-validate-feature-real-features.py — e2e test for spec Inv 25 (BUG-38).
#
# validate-feature.py MUST exit 0 for a feature directory that is otherwise
# valid (correct feature.json, spec.md, contract.md, executable test/run.py)
# but lacks the legacy `docs/bugs/` directory. Per Inv 11, bug storage is
# centralized to `<repo-root>/.claude/bugs/<feature-name>/`; per-feature
# `docs/bugs/` no longer applies.
#
# This is the e2e flavour of `test-validate-no-bugs-root.py`: the existing
# test creates `docs/bugs/` on the fixture (so it does not actually exercise
# the BUG-38 condition). This test omits `docs/bugs/` deliberately.

import json
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VALIDATE = os.path.join(FEATURE_DIR, "scripts/validate-feature.py")


def make_fixture_without_docs_bugs():
    d = tempfile.mkdtemp(prefix="contract-bug-38-fixture-")
    name = os.path.basename(d)

    os.makedirs(os.path.join(d, "specs"), exist_ok=True)
    os.makedirs(os.path.join(d, "test"), exist_ok=True)
    # NOTE: intentionally do NOT create docs/bugs/ — this is the BUG-38 scenario.

    with open(os.path.join(d, "specs/spec.md"), "w") as f:
        f.write("# Fixture spec\nBody.\n")
    with open(os.path.join(d, "specs/contract.md"), "w") as f:
        f.write("# Fixture contract\nBody.\n")

    run_py = os.path.join(d, "test/run.py")
    with open(run_py, "w") as f:
        f.write("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n")
    os.chmod(run_py, 0o755)

    feature_data = {
        "name": name,
        "version": "0.1.0",
        "owner": "test-owner",
        "tdd_state": "spec",
        "summary": "Fixture for BUG-38 e2e test.",
        "surface": {
            "hooks": [],
            "commands": [],
            "agents": [],
            "skills": [],
        },
        "deprecation_criterion": "when test is done",
    }
    with open(os.path.join(d, "feature.json"), "w") as f:
        json.dump(feature_data, f, indent=2)

    return d


fixture = make_fixture_without_docs_bugs()
try:
    proc = subprocess.run(
        ["python3", VALIDATE, fixture],
        capture_output=True, text=True
    )
finally:
    shutil.rmtree(fixture, ignore_errors=True)

if proc.returncode != 0:
    print(
        f"FAIL: validate-feature.py exited {proc.returncode} on a valid feature dir without docs/bugs/ (expected 0)",
        file=sys.stderr,
    )
    print(f"  stdout: {proc.stdout}", file=sys.stderr)
    print(f"  stderr: {proc.stderr}", file=sys.stderr)
    sys.exit(1)

print("test-validate-feature-real-features: PASS (BUG-38 — no docs/bugs/ required)")
