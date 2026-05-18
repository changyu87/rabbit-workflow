#!/usr/bin/env python3
# E2E tests for POLICY-BACKLOG-11, 12.
#
# BACKLOG-11: test-backlog003.py header must name what its assertions guard
#             and when they may be retired (traceability + EOL criterion).
# BACKLOG-12: coding-rules.md Section 3 (Surgical Changes) must clarify
#             that "uncommitted" includes BOTH staged and unstaged work
#             from the current agent session.
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODING_RULES = os.path.join(FEATURE_DIR, "coding-rules.md")
BACKLOG003 = os.path.join(FEATURE_DIR, "test", "test-backlog003.py")

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


# BACKLOG-11: header must name end-of-life criterion + numbering migration role.
def b11():
    with open(BACKLOG003) as f:
        head = "\n".join(f.read().splitlines()[:20])
    if "BACKLOG-003 era" not in head and "numbering migration" not in head:
        ko("b11: test-backlog003.py header does not describe BACKLOG-003 era / numbering migration role")
        return
    if "end-of-life" not in head.lower() and "may be retired" not in head and "retire" not in head.lower():
        ko("b11: test-backlog003.py header does not state when this test may be retired")
        return
    ok("b11: test-backlog003.py header documents role and retirement criterion")


# BACKLOG-12: coding-rules.md Section 3 must say staged + unstaged BOTH count as uncommitted.
def b12():
    with open(CODING_RULES) as f:
        rules = f.read()
    # Find Section 3.
    idx = rules.find("## 3. Surgical Changes")
    if idx < 0:
        ko("b12: coding-rules.md missing '## 3. Surgical Changes' heading")
        return
    sec_end = rules.find("## 4.", idx)
    section = rules[idx:sec_end if sec_end > 0 else len(rules)]
    if "staged" not in section.lower():
        ko("b12: Section 3 does not mention 'staged'")
        return
    if "unstaged" not in section.lower():
        ko("b12: Section 3 does not mention 'unstaged'")
        return
    # The clarification must say BOTH staged and unstaged count as uncommitted.
    if not (
        ("staged and unstaged" in section.lower())
        or ("staged or unstaged" in section.lower())
        or ("both staged" in section.lower())
    ):
        ko("b12: Section 3 does not clarify staged-and-unstaged equivalence")
        return
    ok("b12: coding-rules.md Section 3 clarifies staged + unstaged are both 'uncommitted'")


b11()
b12()

print()
if FAIL == 0:
    print(f"policy-backlog-11/12: {PASS} passed.")
    sys.exit(0)
print(f"policy-backlog-11/12: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
