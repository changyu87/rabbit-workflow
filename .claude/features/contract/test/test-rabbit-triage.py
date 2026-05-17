#!/usr/bin/env python3
# test-rabbit-triage.py — verify rabbit-triage.py builds a valid triage prompt.
#
# Bug.json is stored at the centralized location:
#   <repo-root>/.claude/bugs/<feature-name>/<bug-name>/bug.json
# as written by rabbit-file and per invariant 14.

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

# Use a test-specific feature name to avoid collisions with real feature bugs.
import os as _os
PID = str(_os.getpid())
FIXTURE_FEATURE_NAME = f"contract-triage-basic-test-{PID}"
BUG_NAME = f"test-bug-{PID}"

# Build a minimal fixture feature dir in /tmp.
tmpdir = tempfile.mkdtemp()
FIXTURE = os.path.join(os.path.dirname(tmpdir), FIXTURE_FEATURE_NAME)
os.rename(tmpdir, FIXTURE)

os.makedirs(os.path.join(FIXTURE, "docs/spec"), exist_ok=True)

with open(os.path.join(FIXTURE, "docs/spec/spec.md"), "w") as f:
    f.write("# test-feature spec\nMinimal spec for triage test fixture.\n")

# Create bug.json at the centralized location (per invariant 14 and rabbit-file storage).
CENTRALIZED_BUG_DIR = os.path.join(REPO_ROOT, ".claude/bugs", FIXTURE_FEATURE_NAME, BUG_NAME)
os.makedirs(CENTRALIZED_BUG_DIR, exist_ok=True)

bug_data = {
    "bug_name": "test-bug",
    "status": "open",
    "related_feature": None,
    "summary": "Test bug for triage script validation",
    "filed_by": "test",
    "filed_at": "2026-05-09"
}
with open(os.path.join(CENTRALIZED_BUG_DIR, "bug.json"), "w") as f:
    json.dump(bug_data, f, indent=2)


def cleanup():
    shutil.rmtree(FIXTURE, ignore_errors=True)
    shutil.rmtree(os.path.join(REPO_ROOT, ".claude/bugs", FIXTURE_FEATURE_NAME), ignore_errors=True)


try:
    proc = subprocess.run(
        ["python3", SCRIPT, FIXTURE, BUG_NAME],
        capture_output=True, text=True
    )
    OUTPUT = proc.stdout + proc.stderr
    EXIT_CODE = proc.returncode

    if EXIT_CODE != 0:
        print(f"FAIL: rabbit-triage.py exited with code {EXIT_CODE}", file=sys.stderr)
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

finally:
    cleanup()

if FAIL != 0:
    print("test-rabbit-triage: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-rabbit-triage: all checks passed.")
