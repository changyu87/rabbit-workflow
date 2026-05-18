#!/usr/bin/env python3
# test-python-only-stack.py — assert Python is the sole scripting tech stack.
#
# Invariant 11 (extended): No .sh files exist in scripts/ or scripts/enforcement/.
# Spec accuracy: spec.md must not reference any .sh script files.
# Contract accuracy: contract.md must not reference any .sh script files.
#
# Non-interactive. Exits non-zero on failure.

import os
import sys
import glob

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: No .sh files in scripts/
scripts_dir = os.path.join(FEATURE_DIR, "scripts")
sh_files = glob.glob(os.path.join(scripts_dir, "*.sh")) + \
           glob.glob(os.path.join(scripts_dir, "enforcement", "*.sh"))
if sh_files:
    fail("t1", f"Found .sh files in scripts/ (must be Python-only): {sh_files}")
else:
    ok("t1", "No .sh files in scripts/ or scripts/enforcement/")

# t2: spec.md contains no .sh file path references
spec_path = os.path.join(FEATURE_DIR, "docs/spec/spec.md")
if os.path.isfile(spec_path):
    spec_content = open(spec_path).read()
    # Look for lines listing .sh script files (e.g., "scripts/foo.sh")
    sh_lines = [line for line in spec_content.splitlines()
                if line.strip().startswith("-") and ".sh" in line and "scripts/" in line]
    if sh_lines:
        fail("t2", f"spec.md lists .sh script paths (must be Python-only): {sh_lines}")
    else:
        ok("t2", "spec.md contains no .sh script path references")
else:
    fail("t2", f"spec.md missing at {spec_path}")

# t3: contract.md scripts list contains no .sh files
contract_path = os.path.join(FEATURE_DIR, "docs/spec/contract.md")
if os.path.isfile(contract_path):
    contract_content = open(contract_path).read()
    sh_contract_lines = [line for line in contract_content.splitlines()
                         if ".sh" in line and "scripts/" in line]
    if sh_contract_lines:
        fail("t3", f"contract.md lists .sh script paths (must be Python-only): {sh_contract_lines}")
    else:
        ok("t3", "contract.md contains no .sh script path references")
else:
    fail("t3", f"contract.md missing at {contract_path}")

# t4: spec.md invariants do not reference named .sh scripts as callable/existing tools.
# Exception: invariant 11 documents relink.sh's absence; "does NOT exist" lines are allowed.
if os.path.isfile(spec_path):
    spec_content = open(spec_path).read()
    invariant_sh = []
    for line in spec_content.splitlines():
        if not (line.strip() and line[0].isdigit() and ". `" in line and ".sh`" in line):
            continue
        # Skip lines that document absence (e.g., "does NOT exist") or
        # explicitly forbid .sh as part of a positive Python-only directive
        # (e.g., "not shell scripts").
        if "does NOT exist" in line or "does not exist" in line:
            continue
        if "No `.sh`" in line or "No .sh" in line:
            continue
        if "not shell scripts" in line or "not `.sh`" in line:
            continue
        # Skip lines that forbid an .sh runner (e.g., "not `test/run.sh`")
        # or refer to an .sh script that has been removed.
        if "not `test/run.sh`" in line or "removed `" in line:
            continue
        # Skip lines banning .sh references in scripts.
        if "References to `.sh`" in line and "are banned" in line:
            continue
        # Skip lines that document deleted producers (the .sh names are
        # historical references being forbidden, not callable tools).
        if "deleted producer" in line or "deleted producers" in line:
            continue
        invariant_sh.append(line)
    if invariant_sh:
        fail("t4", f"spec.md invariants still reference .sh scripts as callable tools: {invariant_sh}")
    else:
        ok("t4", "spec.md invariants reference only .py scripts (absence docs excepted)")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-python-only-stack: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-python-only-stack: all checks passed.")
