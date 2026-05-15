#!/usr/bin/env python3
# test-audit-orphan-storage.py — verify audit-orphan-storage.py behavior.
#
# t3: script exists at scripts/audit-orphan-storage.py and is executable
# t4: exits 0 and prints no ORPHAN lines when all subdirs match known features
# t5: exits non-zero and prints ORPHAN when an unknown subdir is present

import os
import sys
import subprocess
import tempfile
import shutil
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
AUDIT = os.path.join(FEATURE_DIR, "scripts/audit-orphan-storage.py")
FAIL = 0

# ---------------------------------------------------------------------------
# t3: script exists and is executable
# ---------------------------------------------------------------------------
if not os.path.isfile(AUDIT):
    print(f"FAIL t3: audit-orphan-storage.py does not exist at {AUDIT}", file=sys.stderr)
    FAIL = 1
elif not os.access(AUDIT, os.X_OK):
    print(f"FAIL t3: audit-orphan-storage.py is not executable: {AUDIT}", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t3: audit-orphan-storage.py exists and is executable")

# If the script doesn't exist, t4 and t5 cannot run meaningfully.
if not os.access(AUDIT, os.X_OK):
    print("test-audit-orphan-storage: FAIL (t3 failed; skipping t4, t5)", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Shared setup: a registry with two known feature names
# ---------------------------------------------------------------------------
REGISTRY_DIR = tempfile.mkdtemp()
registry_data = {
    "schema_version": "1.0.0",
    "owner": "test",
    "features": {
        "feature-alpha": {
            "name": "feature-alpha",
            "version": "0.1.0",
            "owner": "test",
            "tdd_state": "spec",
            "summary": "Test feature alpha",
            "path": ".claude/features/feature-alpha"
        },
        "feature-beta": {
            "name": "feature-beta",
            "version": "0.1.0",
            "owner": "test",
            "tdd_state": "spec",
            "summary": "Test feature beta",
            "path": ".claude/features/feature-beta"
        }
    }
}
with open(os.path.join(REGISTRY_DIR, "registry.json"), "w") as f:
    json.dump(registry_data, f, indent=2)

try:
    # ---------------------------------------------------------------------------
    # t4: all subdirs in temp bugs/backlogs match known features — exits 0, no ORPHAN
    # ---------------------------------------------------------------------------
    BUGS4 = tempfile.mkdtemp()
    BACKLOGS4 = tempfile.mkdtemp()
    os.makedirs(os.path.join(BUGS4, "feature-alpha"), exist_ok=True)
    os.makedirs(os.path.join(BUGS4, "feature-beta"), exist_ok=True)
    os.makedirs(os.path.join(BACKLOGS4, "feature-alpha"), exist_ok=True)

    proc4 = subprocess.run(
        ["python3", AUDIT,
         "--bugs-root", BUGS4,
         "--backlogs-root", BACKLOGS4,
         "--registry", os.path.join(REGISTRY_DIR, "registry.json")],
        capture_output=True, text=True
    )
    OUTPUT4 = proc4.stdout + proc4.stderr
    EXIT4 = proc4.returncode

    shutil.rmtree(BUGS4, ignore_errors=True)
    shutil.rmtree(BACKLOGS4, ignore_errors=True)

    if EXIT4 != 0:
        print(f"FAIL t4: audit-orphan-storage.py exited {EXIT4} for all-known dirs (expected 0)", file=sys.stderr)
        print(f"  output: {OUTPUT4}", file=sys.stderr)
        FAIL = 1
    elif "ORPHAN" in OUTPUT4:
        print("FAIL t4: audit-orphan-storage.py printed ORPHAN when none expected", file=sys.stderr)
        print(f"  output: {OUTPUT4}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t4: audit-orphan-storage.py exits 0 and prints no ORPHAN for known dirs")

    # ---------------------------------------------------------------------------
    # t5: one unknown subdir present — exits non-zero and prints ORPHAN
    # ---------------------------------------------------------------------------
    BUGS5 = tempfile.mkdtemp()
    BACKLOGS5 = tempfile.mkdtemp()
    os.makedirs(os.path.join(BUGS5, "feature-alpha"), exist_ok=True)
    os.makedirs(os.path.join(BUGS5, "unknown-mystery-feature"), exist_ok=True)  # orphan

    proc5 = subprocess.run(
        ["python3", AUDIT,
         "--bugs-root", BUGS5,
         "--backlogs-root", BACKLOGS5,
         "--registry", os.path.join(REGISTRY_DIR, "registry.json")],
        capture_output=True, text=True
    )
    OUTPUT5 = proc5.stdout + proc5.stderr
    EXIT5 = proc5.returncode

    shutil.rmtree(BUGS5, ignore_errors=True)
    shutil.rmtree(BACKLOGS5, ignore_errors=True)

    if EXIT5 == 0:
        print("FAIL t5: audit-orphan-storage.py exited 0 when orphan present (expected non-zero)", file=sys.stderr)
        print(f"  output: {OUTPUT5}", file=sys.stderr)
        FAIL = 1
    elif "ORPHAN" not in OUTPUT5:
        print("FAIL t5: audit-orphan-storage.py did not print ORPHAN when orphan present", file=sys.stderr)
        print(f"  output: {OUTPUT5}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t5: audit-orphan-storage.py exits non-zero and prints ORPHAN for unknown subdir")

finally:
    shutil.rmtree(REGISTRY_DIR, ignore_errors=True)

# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------
if FAIL != 0:
    print("test-audit-orphan-storage: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-audit-orphan-storage: all checks passed.")
