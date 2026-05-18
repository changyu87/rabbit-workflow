#!/usr/bin/env python3
"""test-audit-orphan-backlogs.py — Inv 29.

audit-orphan-storage.py MUST audit both bugs AND backlogs for orphaned
storage. End-to-end: an unknown subdir under backlogs/ MUST trigger an
ORPHAN report and non-zero exit.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
AUDIT = os.path.join(FEATURE_DIR, "scripts/audit-orphan-storage.py")
FAIL = 0

REGISTRY_DIR = tempfile.mkdtemp()
registry_data = {
    "schema_version": "1.0.0",
    "owner": "test",
    "features": {
        "feature-alpha": {
            "name": "feature-alpha", "version": "0.1.0", "owner": "t",
            "tdd_state": "spec", "summary": "s", "path": ".claude/features/feature-alpha"
        }
    }
}
with open(os.path.join(REGISTRY_DIR, "registry.json"), "w") as f:
    json.dump(registry_data, f, indent=2)

try:
    # backlogs/ contains an unknown feature -> orphan
    BUGS = tempfile.mkdtemp()
    BACKLOGS = tempfile.mkdtemp()
    os.makedirs(os.path.join(BUGS, "feature-alpha"), exist_ok=True)
    os.makedirs(os.path.join(BACKLOGS, "unknown-backlog-feature"), exist_ok=True)

    proc = subprocess.run(
        ["python3", AUDIT,
         "--registry", os.path.join(REGISTRY_DIR, "registry.json"),
         "--bugs-root", BUGS,
         "--backlogs-root", BACKLOGS],
        capture_output=True, text=True
    )
    out = proc.stdout + proc.stderr

    if proc.returncode == 0:
        print("FAIL t1: orphan in backlogs/ not detected (exit 0)", file=sys.stderr)
        print(f"  output: {out}", file=sys.stderr)
        FAIL = 1
    elif "ORPHAN" not in out or "backlog" not in out.lower():
        print("FAIL t1: no ORPHAN/backlog line for unknown backlog dir", file=sys.stderr)
        print(f"  output: {out}", file=sys.stderr)
        FAIL = 1
    else:
        print("PASS t1: audit-orphan-storage reports orphan in backlogs/")

    shutil.rmtree(BUGS, ignore_errors=True)
    shutil.rmtree(BACKLOGS, ignore_errors=True)
finally:
    shutil.rmtree(REGISTRY_DIR, ignore_errors=True)

if FAIL:
    print("test-audit-orphan-backlogs: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-audit-orphan-backlogs: all checks passed.")
