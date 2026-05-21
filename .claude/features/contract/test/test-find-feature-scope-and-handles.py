#!/usr/bin/env python3
"""test-find-feature-scope-and-handles.py — Inv 23.

find-feature.py MUST:
  - close all opened file handles (use `with open()`)
  - scan ONLY .claude/features/ for feature directories, NOT any directory
    whose basename happens to be `features`.
"""

import os
import sys
import re
import json
import subprocess
import tempfile
import shutil

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/find-feature.py")

FAIL = 0

# t1: source must not contain bare `json.load(open(...))` — every open() must be in a `with` block.
with open(SCRIPT) as f:
    src = f.read()

# Match `open(` not preceded by `with ` (with bounded look-behind).
# Allow `open(` inside string literals — but we expect none.
bare_open_pattern = re.compile(r'(?<!with )open\(')
# Easier check: count `open(` and count `with open(`. They must be equal.
all_opens = len(re.findall(r'open\(', src))
with_opens = len(re.findall(r'with\s+open\(', src))
if all_opens != with_opens:
    print(f"FAIL t1: {all_opens} open() calls but only {with_opens} are inside `with` blocks", file=sys.stderr)
    FAIL = 1
else:
    print(f"PASS t1: all {all_opens} open() calls use `with` context manager")

# t2: source must restrict scanning to .claude/features/ only — must NOT walk
# any arbitrary directory whose basename is 'features'.
# The old code did `feat_base = os.path.join(repo, entry, 'features')` — that's the bug.
# Acceptable fix: only scan `.claude/features/` (single source). Or scan
# `<project>/features/` only when the project root is properly declared.
# Test: a stray `<repo>/foo/features/bar/feature.json` MUST NOT appear in `list`.
TMPDIR = tempfile.mkdtemp()
try:
    # Create a fake repo with .claude/features/legit and stray foo/features/imposter
    os.makedirs(os.path.join(TMPDIR, ".claude/features/legit"), exist_ok=True)
    with open(os.path.join(TMPDIR, ".claude/features/legit/feature.json"), "w") as f:
        json.dump({"name": "legit", "version": "0.1.0", "owner": "t",
                   "tdd_state": "spec", "summary": "s",
                   "surface": {"hooks": [], "commands": [], "agents": [], "skills": []},
                   "deprecation_criterion": "x"}, f)

    os.makedirs(os.path.join(TMPDIR, "foo/features/imposter"), exist_ok=True)
    with open(os.path.join(TMPDIR, "foo/features/imposter/feature.json"), "w") as f:
        json.dump({"name": "imposter", "version": "0.1.0", "owner": "t",
                   "tdd_state": "spec", "summary": "s",
                   "surface": {"hooks": [], "commands": [], "agents": [], "skills": []},
                   "deprecation_criterion": "x"}, f)

    proc = subprocess.run(
        ["python3", SCRIPT, TMPDIR, "list"],
        capture_output=True, text=True,
    )
    listed = [line.strip() for line in proc.stdout.split("\n") if line.strip()]
    if "legit" not in listed:
        print(f"FAIL t2: legit feature not found in list (got {listed})", file=sys.stderr)
        FAIL = 1
    if "imposter" in listed:
        print(f"FAIL t2: imposter feature (under foo/features/) leaked into list (got {listed})", file=sys.stderr)
        FAIL = 1
    if "legit" in listed and "imposter" not in listed:
        print("PASS t2: scope restricted to .claude/features/ only")
finally:
    shutil.rmtree(TMPDIR, ignore_errors=True)

if FAIL:
    print("test-find-feature-scope-and-handles: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-find-feature-scope-and-handles: all checks passed.")
