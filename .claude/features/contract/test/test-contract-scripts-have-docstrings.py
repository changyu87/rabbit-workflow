#!/usr/bin/env python3
"""test-contract-scripts-have-docstrings.py — BUG-23 / Inv 13

End-to-end test that every Python script under .claude/features/contract/scripts/
(and scripts/enforcement/) has a module-level docstring. Specifically verifies
policy-block.py so that print_usage() prints non-empty text.

t1: policy-block.py has a non-empty module docstring (ast-level).
t2: invoking policy-block.py --help prints non-empty text on stderr.
t3: every .py under scripts/ (and scripts/enforcement/) has a non-empty
    module-level docstring.
"""

import ast
import os
import subprocess
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS_DIR = os.path.join(FEATURE_DIR, "scripts")
POLICY_BLOCK = os.path.join(SCRIPTS_DIR, "policy-block.py")

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS t{n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    FAIL += 1


def module_docstring(path):
    with open(path) as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    return ast.get_docstring(tree)


# t1: policy-block.py has non-empty module docstring
ds = module_docstring(POLICY_BLOCK)
if ds and ds.strip():
    ok(1, "policy-block.py has non-empty module docstring")
else:
    fail_t(1, f"policy-block.py module docstring is missing/empty: {ds!r}")

# t2: policy-block.py --help prints non-empty text
r2 = subprocess.run(["python3", POLICY_BLOCK, "--help"], capture_output=True, text=True)
help_output = (r2.stdout or "") + (r2.stderr or "")
if help_output.strip() and "None" not in help_output.split("\n")[0]:
    ok(2, "policy-block.py --help prints non-empty text")
else:
    fail_t(2, f"policy-block.py --help output is empty or 'None': {help_output!r}")

# t3: every .py under scripts/ has a module docstring
missing = []
for dirpath, dirnames, filenames in os.walk(SCRIPTS_DIR):
    for fname in filenames:
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(dirpath, fname)
        ds = module_docstring(fpath)
        if not ds or not ds.strip():
            missing.append(os.path.relpath(fpath, FEATURE_DIR))

if not missing:
    ok(3, "all .py scripts under scripts/ have non-empty module docstrings")
else:
    fail_t(3, f"scripts missing module docstring: {missing}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
