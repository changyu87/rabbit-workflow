#!/usr/bin/env python3
# test-rabbit-triage-centralized.py — assert rabbit-triage.py finds bug.json at
# <repo-root>/.claude/bugs/<feature-name>/<bug-name>/bug.json (centralized storage).
#
# Invariant 14: rabbit-triage.py locates bug.json in the centralized .claude/bugs/
# directory, not in <feature-dir>/docs/bugs/.
#
# R3-compliant: no interactive constructs, fully automated.

import os
import sys
import subprocess
import tempfile
import shutil
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/rabbit-triage.py")

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

FAIL = 0

PID = str(os.getpid())
FIXTURE_FEATURE_NAME = f"contract-triage-test-fixture-{PID}"

# Build a minimal fixture feature dir in /tmp (spec only, no docs/bugs/).
tmpdir = tempfile.mkdtemp()
os.makedirs(os.path.join(tmpdir, "docs/spec"), exist_ok=True)
with open(os.path.join(tmpdir, "docs/spec/spec.md"), "w") as f:
    f.write("# contract-triage-test-fixture spec\nMinimal spec for centralized-triage test fixture.\n")

# Override FEATURE_BASENAME by using the fixture feature name as the feature dir basename.
FIXTURE_NAMED_DIR = os.path.join(os.path.dirname(tmpdir), FIXTURE_FEATURE_NAME)
os.rename(tmpdir, FIXTURE_NAMED_DIR)
FIXTURE_FEATURE_DIR = FIXTURE_NAMED_DIR

BUG_NAME = f"FIXTURE-BUG-{PID}"

# Create bug.json at the centralized location in the REAL repo root.
CENTRALIZED_BUG_DIR = os.path.join(REPO_ROOT, ".claude/bugs", FIXTURE_FEATURE_NAME, BUG_NAME)
os.makedirs(CENTRALIZED_BUG_DIR, exist_ok=True)

bug_data = {
    "bug_name": "FIXTURE-BUG",
    "status": "open",
    "related_feature": "contract-triage-test-fixture",
    "summary": "Centralized bug for triage script validation",
    "filed_by": "test",
    "filed_at": "2026-05-13"
}
with open(os.path.join(CENTRALIZED_BUG_DIR, "bug.json"), "w") as f:
    json.dump(bug_data, f, indent=2)


def cleanup():
    shutil.rmtree(FIXTURE_FEATURE_DIR, ignore_errors=True)
    shutil.rmtree(os.path.join(REPO_ROOT, ".claude/bugs", FIXTURE_FEATURE_NAME), ignore_errors=True)


try:
    # Verify the old incorrect path does NOT have a bug.json.
    OLD_BUG_PATH = os.path.join(FIXTURE_FEATURE_DIR, "docs/bugs", BUG_NAME, "bug.json")
    if os.path.isfile(OLD_BUG_PATH):
        print(f"FAIL: test setup error — bug.json exists at old path {OLD_BUG_PATH}", file=sys.stderr)
        cleanup()
        sys.exit(1)

    # Call rabbit-triage.py — uses git to derive REPO_ROOT from the script's own location.
    proc = subprocess.run(
        ["python3", SCRIPT, FIXTURE_FEATURE_DIR, BUG_NAME],
        capture_output=True, text=True
    )
    OUTPUT = proc.stdout + proc.stderr
    EXIT_CODE = proc.returncode

    if EXIT_CODE != 0:
        print(f"FAIL: rabbit-triage.py exited {EXIT_CODE} when given centralized bug path", file=sys.stderr)
        print(f"Output: {OUTPUT}", file=sys.stderr)
        FAIL = 1

    def check_contains(label, pattern):
        global FAIL
        if pattern not in OUTPUT:
            print(f"FAIL: output does not contain '{pattern}' (check: {label})", file=sys.stderr)
            FAIL = 1

    check_contains("sentinel line", "RABBIT-POLICY-BLOCK-v1")
    check_contains("triage request header", "TRIAGE REQUEST")
    check_contains("bug name", BUG_NAME)
    check_contains("bug content present", "Centralized bug for triage script validation")

finally:
    cleanup()

if FAIL != 0:
    print("test-rabbit-triage-centralized: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-rabbit-triage-centralized: all checks passed.")
