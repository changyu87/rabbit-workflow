#!/usr/bin/env python3
"""test-coding-rules-numbering.py — Verify coding-rules.md uses standalone
numbering (1-5) and a clean heading (no 'Part II', no '## Code-Editing
Discipline').

Role / traceability: this test guards the structural outcome of the BACKLOG-003
era numbering migration (a pre-rabbit-file workflow ticket ID; no current
`BACKLOG-003` lives under `rabbit/features/policy/backlogs/`). It documents
the policy-rule-number contract, not a presently-open ticket.

Traces: POLICY-BACKLOG-003 (numbering migration), POLICY-BACKLOG-11 (EOL
        criterion requirement), POLICY-BACKLOG-14 (rename to behavior-first
        filename per Inv 9; originally test-backlog003.py).

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: per philosophy.md Designed Deprecation, this file may
be retired once `test-policy-invariants.py` (or successor) covers the same
numbering / heading assertions for `coding-rules.md`. Tracked by
POLICY-BACKLOG-11.
"""
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODING_RULES = os.path.join(FEATURE_DIR, "coding-rules.md")

with open(CODING_RULES) as f:
    content = f.read()

FAILURES = 0

# --- Group A: Rule numbering ---

# t1: must NOT contain '### 4. Think Before Coding' (old cross-file numbering gone)
if re.search(r'### 4\. Think Before Coding', content):
    print("FAIL: t1: coding-rules.md should NOT contain '### 4. Think Before Coding' (cross-file numbering)")
    FAILURES += 1
else:
    print("PASS: t1: coding-rules.md does not contain '### 4. Think Before Coding'")

# t2: must contain '## 1.' (first rule starts at 1, promoted to H2)
if re.search(r'^## 1\.', content, re.MULTILINE):
    print("PASS: t2: coding-rules.md contains '## 1.'")
else:
    print("FAIL: t2: coding-rules.md should contain '## 1.' (rules start at 1)")
    FAILURES += 1

# t3: rule count is exactly 5 (POLICY-BUG-1 / POLICY-BACKLOG-1/5: fifth rule added).
# The fifth rule is 'Output Hygiene'; no sixth rule exists yet.
if re.search(r'^## 6\.', content, re.MULTILINE):
    print("FAIL: t3: coding-rules.md should NOT contain '## 6.' (rules must stop at 5)")
    FAILURES += 1
else:
    print("PASS: t3: coding-rules.md does not contain '## 6.' (rules stop at 5)")

# t4: must NOT contain '### 8.' (old last rule gone)
if re.search(r'### 8\.', content):
    print("FAIL: t4: coding-rules.md should NOT contain '### 8.' (old numbering)")
    FAILURES += 1
else:
    print("PASS: t4: coding-rules.md does not contain '### 8.'")

# --- Group B: Part II heading ---

# t5: must NOT contain 'Part II'
if "Part II" in content:
    print("FAIL: t5: coding-rules.md should NOT contain 'Part II'")
    FAILURES += 1
else:
    print("PASS: t5: coding-rules.md does not contain 'Part II'")

# t6: must NOT contain '## Code-Editing Discipline' (heading removed in restructure)
if re.search(r'^## Code-Editing Discipline$', content, re.MULTILINE):
    print("FAIL: t6: coding-rules.md should NOT contain '## Code-Editing Discipline' (heading removed)")
    FAILURES += 1
else:
    print("PASS: t6: coding-rules.md does not contain '## Code-Editing Discipline'")

# --- Summary ---
print()
if FAILURES == 0:
    print("All tests passed.")
    sys.exit(0)
else:
    print(f"{FAILURES} test(s) failed.")
    sys.exit(1)
