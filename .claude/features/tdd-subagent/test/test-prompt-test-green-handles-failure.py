#!/usr/bin/env python3
"""Inv 46 — dispatched-subagent template MUST emit test_result: fail on
nonzero run.py exit; MUST NOT hard-code a `pass` literal for test_result;
template_version MUST be bumped to >= 1.1.0.

The template lives at
.claude/features/contract/templates/prompts/tdd-subagent.txt (per contract
Inv 57). This test reads that file and asserts the five properties named
in the implementation suggestion for TDD-SUBAGENT-BACKLOG-20.
"""
import os
import re
import sys

from _helpers import REPO_ROOT, report

TEMPLATE_PATH = os.path.join(
    REPO_ROOT,
    ".claude", "features", "contract", "templates", "prompts",
    "tdd-subagent.txt",
)

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


if not os.path.isfile(TEMPLATE_PATH):
    print(f"FATAL: template not found at {TEMPLATE_PATH}")
    sys.exit(1)

with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = f.read()

# t-no-pass-literal-yaml: YAML-form 'test_result: pass' MUST NOT appear.
if "test_result: pass" not in template:
    ok("t-no-pass-literal-yaml: YAML literal 'test_result: pass' absent")
else:
    ko("t-no-pass-literal-yaml: YAML literal 'test_result: pass' still present in template")

# t-no-pass-literal-json: JSON-form '"test_result": "pass"' MUST NOT appear.
if '"test_result": "pass"' not in template:
    ok("t-no-pass-literal-json: JSON literal '\"test_result\": \"pass\"' absent")
else:
    ko("t-no-pass-literal-json: JSON literal '\"test_result\": \"pass\"' still present in template")

# t-pass-or-fail-placeholder-yaml: YAML 'test_result: <pass|fail>' MUST appear.
if re.search(r"test_result:\s*<pass\|fail>", template):
    ok("t-pass-or-fail-placeholder-yaml: YAML 'test_result: <pass|fail>' placeholder present")
else:
    ko("t-pass-or-fail-placeholder-yaml: YAML 'test_result: <pass|fail>' placeholder missing")

# t-pass-or-fail-placeholder-json: JSON '"test_result": "<pass|fail>"' MUST appear.
if '"test_result": "<pass|fail>"' in template:
    ok("t-pass-or-fail-placeholder-json: JSON '\"test_result\": \"<pass|fail>\"' placeholder present")
else:
    ko("t-pass-or-fail-placeholder-json: JSON '\"test_result\": \"<pass|fail>\"' placeholder missing")

# t-step6-nonzero-conditional: STEP 6 section MUST contain a nonzero-exit
# branch that emits a fail-HANDOFF (mentioning both 'test_result' and 'fail'
# in the same region).
step6_match = re.search(r"STEP 6 — TEST-GREEN", template)
step7_match = re.search(r"STEP 7 — UNLOCK", template)
if not step6_match or not step7_match:
    ko("t-step6-nonzero-conditional: cannot locate STEP 6 / STEP 7 banners")
else:
    step6_region = template[step6_match.start():step7_match.start()]
    region_lower = step6_region.lower()
    has_nonzero_branch = (
        ("nonzero" in region_lower and "exit" in region_lower)
        or "exits 1" in region_lower
        or "exits nonzero" in region_lower
    )
    has_fail_handoff = ("test_result" in step6_region) and re.search(
        r"\bfail\b", step6_region
    )
    if has_nonzero_branch and has_fail_handoff:
        ok("t-step6-nonzero-conditional: STEP 6 has nonzero-exit branch emitting fail-HANDOFF")
    else:
        ko(
            "t-step6-nonzero-conditional: STEP 6 missing nonzero-exit branch "
            f"(nonzero_branch={has_nonzero_branch}, fail_handoff={bool(has_fail_handoff)})"
        )

# t-template-version-bump: the first non-empty line MUST declare
# template_version 1.1.0 or higher (minor or major bump).
first_line = template.splitlines()[0] if template.splitlines() else ""
m = re.match(r"#\s*template_version:\s*(\d+)\.(\d+)\.(\d+)", first_line)
if not m:
    ko(f"t-template-version-bump: first line missing template_version marker: {first_line!r}")
else:
    major, minor, _patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if (major, minor) >= (1, 1):
        ok(f"t-template-version-bump: template_version is {major}.{minor}.{_patch} (>= 1.1.0)")
    else:
        ko(f"t-template-version-bump: template_version is {major}.{minor}.{_patch}, expected >= 1.1.0")

report(passed, failed)
