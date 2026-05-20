#!/usr/bin/env python3
"""test-dispatch-feature-edit-py-only.py — BUG-39.

dispatch-feature-edit.py's TDD_GAP prompt template must instruct subagents to
name regression tests with the `.py` extension (the Python-only stack per
Inv 11/17). The legacy `.sh` extension reference would lead subagents to
scaffold shell test files that immediately violate the contract.

End-to-end: read the dispatch-feature-edit.py source and assert the prompt
template does NOT reference `.sh` as a regression-test file extension AND
DOES reference `.py`.
"""

import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/dispatch-feature-edit.py")

FAIL = 0

with open(SCRIPT) as f:
    src = f.read()

# t1: prompt template must not reference a `.sh` test-file extension in the
# TDD_GAP regression-test naming guidance.
sh_test_pattern = re.compile(r"test-\{?[^}]*\}?[^\s]*\.sh")
matches = sh_test_pattern.findall(src)
if matches:
    print(f"FAIL t1: dispatch-feature-edit.py references .sh test file(s): {matches}", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: dispatch-feature-edit.py contains no .sh test-file references")

# t2: prompt template must reference `.py` as the regression-test extension.
py_test_pattern = re.compile(r"test-\{?[^}]*\}?[^\s]*\.py")
if not py_test_pattern.search(src):
    print("FAIL t2: dispatch-feature-edit.py prompt template lacks .py test-file reference", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t2: dispatch-feature-edit.py prompt template references .py test files")

if FAIL:
    print("test-dispatch-feature-edit-py-only: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-dispatch-feature-edit-py-only: all checks passed.")
