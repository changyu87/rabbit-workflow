#!/usr/bin/env python3
"""test-dispatch-script.py — rabbit-spec Inv 3.

Invokes dispatch-spec-creator.py in both modes (standalone — no globs, and
plugin — with globs) and asserts each emits a prompt-file path on stdout
and exits 0.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/dispatch-spec-creator.py")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(FEATURE_DIR)))

if not os.access(SCRIPT, os.X_OK):
    print(f"FAIL: dispatch script not executable: {SCRIPT}", file=sys.stderr)
    sys.exit(1)

errors = []

# Plugin mode: with a glob that matches at least one file
r = subprocess.run(
    ["python3", SCRIPT, "--feature-name", "test-foo", "--paths", "*.md"],
    cwd=REPO_ROOT, capture_output=True, text=True,
)
if r.returncode != 0:
    errors.append(f"plugin mode exit nonzero: {r.returncode}; stderr={r.stderr}")
elif not r.stdout.strip():
    errors.append(f"plugin mode produced no stdout")
elif not os.path.isfile(r.stdout.strip()):
    errors.append(f"plugin mode stdout '{r.stdout.strip()}' is not an existing file")

# Standalone mode: empty paths
r = subprocess.run(
    ["python3", SCRIPT, "--feature-name", "test-bar", "--paths", ""],
    cwd=REPO_ROOT, capture_output=True, text=True,
)
if r.returncode != 0:
    errors.append(f"standalone mode exit nonzero: {r.returncode}; stderr={r.stderr}")
elif not r.stdout.strip():
    errors.append(f"standalone mode produced no stdout")
elif not os.path.isfile(r.stdout.strip()):
    errors.append(f"standalone mode stdout '{r.stdout.strip()}' is not an existing file")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: dispatch-spec-creator.py handles both plugin and standalone modes")
