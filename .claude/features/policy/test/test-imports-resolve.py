#!/usr/bin/env python3
"""test-imports-resolve.py — assert every @-import in any CLAUDE.md resolves.

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when Claude Code enforces @-import resolution natively.
"""
import os
import re
import subprocess
import sys

RABBIT_ROOT = os.environ.get("RABBIT_ROOT")
if not RABBIT_ROOT:
    result = subprocess.run(
        ["git", "-C", os.path.dirname(__file__), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    RABBIT_ROOT = result.stdout.strip()

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


# Find all CLAUDE.md files
claude_mds = []
for root, dirs, files in os.walk(RABBIT_ROOT):
    dirs[:] = [d for d in dirs if d not in ("archive", ".git")]
    for fname in files:
        if fname == "CLAUDE.md":
            claude_mds.append(os.path.join(root, fname))

for claude_md in claude_mds:
    try:
        with open(claude_md) as f:
            lines = f.readlines()
    except OSError:
        continue
    for line in lines:
        m = re.match(r'^(@[^\s]+)', line)
        if not m:
            continue
        import_path = m.group(1)
        resolved = import_path.lstrip("@")
        full = os.path.join(RABBIT_ROOT, resolved)
        if os.path.exists(full):
            ok(f"{claude_md}: {resolved}")
        else:
            ko(f"{claude_md}: {resolved} DOES NOT EXIST")

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
