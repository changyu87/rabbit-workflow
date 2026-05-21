#!/usr/bin/env python3
"""Inv 94 / RABBIT-CAGE-BACKLOG-25 part 5.

Every script path declared in
.claude/features/rabbit-cage/docs/spec/contract.md under
`provides.scripts` MUST exist on disk.

The intent is to catch contract-vs-reality drift of the kind that
previously let contract.md retain `relink.sh` and
`dispatch-feature-edit.sh` long after those scripts were deleted.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the equivalent existence check is exposed
    as a contract-feature-owned library check that sweeps every
    feature's contract.md (the rabbit-cage-only scope is interim).
"""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

CONTRACT_MD = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/contract.md"
)

failures = 0


def fail(msg):
    global failures
    failures += 1
    print(f"FAIL: {msg}", file=sys.stderr)


with open(CONTRACT_MD) as f:
    text = f.read()

m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
if not m:
    fail("contract.md has no fenced JSON block")
    print()
    print(f"Results: {failures} failure(s)")
    sys.exit(1)

try:
    data = json.loads(m.group(1))
except Exception as exc:
    fail(f"contract.md JSON block does not parse: {exc}")
    print()
    print(f"Results: {failures} failure(s)")
    sys.exit(1)

provides = data.get("provides", {}) or {}
scripts = provides.get("scripts", []) or []

if not scripts:
    fail("contract.md provides.scripts is empty — rabbit-cage owns several scripts and should declare them")
else:
    missing = []
    for entry in scripts:
        # Entries may be either bare path strings or objects with a "path" key.
        path = entry if isinstance(entry, str) else (entry.get("path") if isinstance(entry, dict) else None)
        if not path:
            fail(f"contract.md provides.scripts entry has no path: {entry!r}")
            continue
        abspath = os.path.join(REPO_ROOT, path)
        if not os.path.isfile(abspath):
            missing.append(path)
    if missing:
        fail(f"contract.md provides.scripts paths NOT present on disk: {missing}")

if failures == 0:
    print("PASS: every contract.md provides.scripts path exists on disk")
    print()
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print()
    print(f"Results: {failures} failure(s)")
    sys.exit(1)
