#!/usr/bin/env python3
"""Tests for confirm-token override approval flow in spec/contract."""
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SPEC = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
CONTRACT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/contract.md")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


print("test-RABBIT-CAGE-19-confirm-token-override.py")
print()
print("=== SPEC: human-only authoring restriction removed ===")

spec = read(SPEC)
contract = read(CONTRACT)

# t1 (BUG-76: regex broadened to catch reformulations of the prohibited concept)
# Original literal "only a human creates this file" would silently pass on rewordings like
# "only a human creates the file" or "only humans create this file" — the prohibition
# would return but the assertion would not notice. Match the concept, not the wording.
if not re.search(r"only\s+(a\s+)?humans?.*creat\w*.*(this|the)\s+file", spec, re.IGNORECASE):
    ok("spec does not contain 'only ... human ... creates ... file' restriction")
else:
    fail_t("spec still contains 'only ... human ... creates ... file' wording -- human-only restriction not removed")

# t2
if not re.search(r"Authoring.*rabbit-scope-override.*only a human", spec):
    ok("spec does not contain old human-only authoring out-of-scope bullet")
else:
    fail_t("spec still contains old human-only authoring out-of-scope bullet")

print()
print("=== SPEC: confirm-token flow documented ===")

# t3
if re.search(r"confirm.?token", spec, re.IGNORECASE):
    ok("spec documents confirm-token approval flow")
else:
    fail_t("spec does NOT document confirm-token approval flow")

# t4
if re.search(r"(main session|Claude).*write.*rabbit-scope-override|rabbit-scope-override.*write.*(main session|Claude)", spec):
    ok("spec states main session/Claude may write .rabbit-scope-override after approval")
else:
    fail_t("spec does not state main session/Claude may write .rabbit-scope-override after approval")

# t5
if re.search(r"in-conversation", spec):
    ok("spec references in-conversation approval")
else:
    fail_t("spec does NOT reference in-conversation approval")

print()
print("=== CONTRACT: never list updated ===")

# t6
if "creates .rabbit-scope-override (human-only authoring)" not in contract:
    ok("contract never-list does not forbid Claude writing .rabbit-scope-override")
else:
    fail_t("contract never-list still contains 'creates .rabbit-scope-override (human-only authoring)'")

print()
print("=== CONTRACT: runtime_markers writer updated ===")

# t7
if re.search(r'"writer".*Claude', contract):
    ok("contract runtime_markers writer field includes Claude for .rabbit-scope-override")
else:
    fail_t("contract runtime_markers writer field does NOT include Claude for .rabbit-scope-override")

# t8
if re.search(r"in-conversation", contract):
    ok("contract runtime_markers references in-conversation approval condition")
else:
    fail_t("contract runtime_markers does NOT reference in-conversation approval condition")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
