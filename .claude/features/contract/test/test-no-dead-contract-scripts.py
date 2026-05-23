#!/usr/bin/env python3
"""test-no-dead-contract-scripts.py — Inv 34 / CONTRACT-BACKLOG-24

E2E test that every Python script under
`.claude/features/contract/scripts/` (excluding `enforcement/`) has at least
one production caller outside the contract feature itself.

A "production caller" is a reference to the script's basename anywhere in
`.claude/`, excluding:
  - `.claude/archive/`
  - any `__pycache__/`
  - the contract feature's own `scripts/`, `tests/`, `test/`, `docs/spec/`,
    and `build-contract.json` (self-references, including spec/contract.md
    that merely declare the surface).

Also verifies that the five scripts deleted by CONTRACT-BACKLOG-24 are
absent:
  - audit-orphan-storage.py
  - check-maps-consistent.py
  - render-template.py
  - dispatch-spec-update.py
  - rabbit-triage.py

And that the orphan `tests/` plural directory and committed `.pyc` cache
file are gone.

Exit 0 on all pass; 1 on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when an automated dead-code detector spanning the
whole repo is wired into the Stop hook.
"""

import os
import subprocess
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
CLAUDE_DIR = os.path.join(REPO_ROOT, ".claude")
CONTRACT_SCRIPTS_DIR = os.path.join(FEATURE_DIR, "scripts")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}", file=sys.stderr)
    FAIL = 1


# --- t1: deleted scripts are absent ---
DEAD_SCRIPTS = [
    "audit-orphan-storage.py",
    "check-maps-consistent.py",
    "render-template.py",
    "dispatch-spec-update.py",
    "rabbit-triage.py",
]
for name in DEAD_SCRIPTS:
    path = os.path.join(CONTRACT_SCRIPTS_DIR, name)
    if os.path.exists(path):
        ko(f"t1: dead script still present: {path}")
    else:
        ok(f"t1: dead script absent: {name}")

# --- t2: orphan plural tests/ directory is absent ---
plural_tests = os.path.join(FEATURE_DIR, "tests")
if os.path.exists(plural_tests):
    ko(f"t2: orphan plural tests/ directory still present: {plural_tests}")
else:
    ok("t2: orphan plural tests/ directory absent")

# --- t3: no .pyc / __pycache__ artifacts are git-tracked under contract ---
# pyc files may regenerate on Python import; only tracking is the failure mode.
result = subprocess.run(
    ["git", "-C", REPO_ROOT, "ls-files", ".claude/features/contract/"],
    capture_output=True, text=True,
)
tracked_pyc = [
    p for p in result.stdout.splitlines()
    if p.endswith(".pyc") or "/__pycache__/" in p
]
if tracked_pyc:
    ko(f"t3: pyc / __pycache__ artifacts tracked in git: {tracked_pyc}")
else:
    ok("t3: no pyc / __pycache__ artifacts tracked in git")

# --- t4: registry.json.schema.json is absent ---
reg_schema = os.path.join(FEATURE_DIR, "schemas", "registry.json.schema.json")
if os.path.exists(reg_schema):
    ko(f"t4: dead registry.json.schema.json still present: {reg_schema}")
else:
    ok("t4: dead registry.json.schema.json absent")

# --- t5: every remaining script under scripts/ (not enforcement/) has a
# production caller. ---
def has_production_caller(basename):
    """Grep .claude for basename, exclude self-references and noise."""
    result = subprocess.run(
        ["grep", "-rln", basename, CLAUDE_DIR],
        capture_output=True, text=True,
    )
    matches = [p for p in result.stdout.splitlines() if p]
    qualifying = []
    for p in matches:
        norm = os.path.normpath(p)
        if "/archive/" in norm:
            continue
        if "/__pycache__/" in norm:
            continue
        # Skip the script file itself
        if os.path.basename(norm) == basename:
            continue
        # Skip contract self-references: the script's own feature scripts,
        # tests, and spec/contract surface listings.
        if norm.startswith(CONTRACT_SCRIPTS_DIR + os.sep):
            continue
        if norm.startswith(os.path.join(FEATURE_DIR, "test") + os.sep):
            continue
        if norm.startswith(os.path.join(FEATURE_DIR, "tests") + os.sep):
            continue
        if norm.startswith(os.path.join(FEATURE_DIR, "docs", "spec") + os.sep):
            continue
        qualifying.append(norm)
    return qualifying


# KNOWN_ISSUES — scripts pending a production caller. Follow the Inv 38
# pattern: add only when a multi-plan cycle is in flight, remove once the
# caller lands. Each entry must name the plan / backlog that will close it.
KNOWN_ISSUES = {
    # Added by Plan A of CONTRACT-BACKLOG-36 (meta-contract foundation).
    # The CLI shim is user-invocable today but has no programmatic caller
    # until Plan C wires it into rabbit-cage's install dispatcher OR Plan E
    # adds it to rabbit-feature-audit. Remove this entry once either lands.
    "validate-meta-contract.py",
}

remaining = []
for fname in sorted(os.listdir(CONTRACT_SCRIPTS_DIR)):
    full = os.path.join(CONTRACT_SCRIPTS_DIR, fname)
    if not os.path.isfile(full):
        continue
    if not fname.endswith(".py"):
        continue
    remaining.append(fname)

for fname in remaining:
    if fname in KNOWN_ISSUES:
        ok(f"t5: {fname} skipped (KNOWN_ISSUES; pending production caller)")
        continue
    callers = has_production_caller(fname)
    if callers:
        ok(f"t5: {fname} has production caller(s): {callers[:2]}{'...' if len(callers) > 2 else ''}")
    else:
        ko(f"t5: {fname} has NO production caller — dead code, must be deleted")


if FAIL:
    print("\ntest-no-dead-contract-scripts: FAIL", file=sys.stderr)
    sys.exit(1)
print("\ntest-no-dead-contract-scripts: all checks passed.")
