#!/usr/bin/env python3
# test-validate-feature-real-features.py — e2e test for spec Inv 39.
#
# validate-feature.py MUST exit 0 on every real feature directory under
# .claude/features/ in this repo. Per Inv 14, bug storage is centralized
# to .claude/bugs/<feature-name>/; per-feature docs/bugs/ no longer applies.
# A spurious requirement for docs/bugs/ fails every feature except those
# that happen to retain a legacy docs/bugs/ directory.

import os
import sys
import subprocess

REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..")
)
FEATURES_DIR = os.path.join(REPO_ROOT, ".claude", "features")
VALIDATE = os.path.join(
    REPO_ROOT, ".claude", "features", "contract", "scripts", "validate-feature.py"
)

failures = []
checked = 0

for entry in sorted(os.listdir(FEATURES_DIR)):
    feature_dir = os.path.join(FEATURES_DIR, entry)
    if not os.path.isdir(feature_dir):
        continue
    if not os.path.isfile(os.path.join(feature_dir, "feature.json")):
        # Skip non-feature directories (README.md, policy/, etc. without feature.json).
        continue
    checked += 1
    proc = subprocess.run(
        ["python3", VALIDATE, feature_dir],
        capture_output=True, text=True
    )
    if proc.returncode != 0:
        failures.append((feature_dir, proc.returncode, proc.stdout + proc.stderr))

if checked == 0:
    print("FAIL: no real features found to validate", file=sys.stderr)
    sys.exit(1)

if failures:
    print(f"FAIL: validate-feature.py failed on {len(failures)} real feature(s):", file=sys.stderr)
    for fd, rc, out in failures:
        print(f"  {fd}: exit={rc}", file=sys.stderr)
        for line in out.splitlines():
            print(f"    {line}", file=sys.stderr)
    sys.exit(1)

print(f"test-validate-feature-real-features: PASS ({checked} feature(s) validated)")
