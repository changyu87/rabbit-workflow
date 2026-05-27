#!/usr/bin/env python3
# test-cli-naming-convention.py — assert spec declares CLI naming convention
# (Inv 11: boolean values use true/false exclusively; Inv 12: positive-streamlined names).
#
# E2E spec-text assertions per impl-suggestion-contract.json.

import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SPEC_PATH = os.path.join(FEATURE_DIR, "docs/spec/spec.md")
FAIL = 0

with open(SPEC_PATH, "r") as f:
    SPEC = f.read()


def check(label, cond):
    global FAIL
    if not cond:
        print(f"FAIL: {label}", file=sys.stderr)
        FAIL = 1


# Locate the "CLI Naming Convention" section.
section_match = re.search(
    r"## CLI Naming Convention\b(.*?)(?=^## |\Z)",
    SPEC,
    re.DOTALL | re.MULTILINE,
)
check("spec contains '## CLI Naming Convention' section", section_match is not None)

SECTION = section_match.group(1) if section_match else ""

# Locate invariant 11 — a numbered list item starting with "11." in the In Scope list.
inv11_match = re.search(r"^11\.\s+(.+?)(?=^\d+\.\s|\Z)", SPEC, re.DOTALL | re.MULTILINE)
check("spec contains invariant 11", inv11_match is not None)
INV11 = inv11_match.group(1) if inv11_match else ""

# Locate invariant 12.
inv12_match = re.search(r"^12\.\s+(.+?)(?=^\d+\.\s|\Z|^##)", SPEC, re.DOTALL | re.MULTILINE)
check("spec contains invariant 12", inv12_match is not None)
INV12 = inv12_match.group(1) if inv12_match else ""

# Inv 11 text — must mention true and false as the canonical boolean values,
# and prohibit at least `enabled`/`disabled`.
check("Inv 11 mentions 'true'", "true" in INV11)
check("Inv 11 mentions 'false'", "false" in INV11)
check("Inv 11 prohibits 'enabled'", "enabled" in INV11)
check("Inv 11 prohibits 'disabled'", "disabled" in INV11)

# Inv 12 text — must prohibit each negating prefix.
check("Inv 12 prohibits 'no-' prefix", "no-" in INV12)
check("Inv 12 prohibits 'disable-' prefix", "disable-" in INV12)
check("Inv 12 prohibits 'skip-' prefix", "skip-" in INV12)
check("Inv 12 prohibits 'without-' prefix", "without-" in INV12)

# CLI Naming Convention section — Rule 1 must declare true/false.
check("Section Rule 1 contains 'true'", "true" in SECTION)
check("Section Rule 1 contains 'false'", "false" in SECTION)

# Section must list the prohibited boolean vocabularies (enabled/disabled, on/off, yes/no).
for token in ["enabled", "disabled", "on", "off", "yes", "no"]:
    check(f"Section lists prohibited boolean value '{token}'", token in SECTION)

# Section must list each prohibited negating prefix.
for token in ["no-", "disable-", "skip-", "without-"]:
    check(f"Section lists prohibited prefix '{token}'", token in SECTION)

# Neither `enabled` nor `disabled` may appear as a recommended/PREFER example.
# Inspect any line beginning with "PREFER" or "- PREFER" in the section.
prefer_lines = [
    line for line in SECTION.splitlines()
    if re.match(r"\s*-?\s*PREFER\b", line)
]
check("section contains at least one PREFER example", len(prefer_lines) > 0)
for line in prefer_lines:
    check(
        f"PREFER line does not recommend 'enabled': {line.strip()!r}",
        "enabled" not in line,
    )
    check(
        f"PREFER line does not recommend 'disabled': {line.strip()!r}",
        "disabled" not in line,
    )

# CONTRACT-BACKLOG-41 regression: the retired `--human-approval-gate` CLI
# flag (removed from tdd-subagent in v5.0.0) must NOT appear anywhere in the
# CLI Naming Convention section. The flag has no live CLI surface, so
# citing it as a canonical example creates documentation drift.
check(
    "CLI Naming Convention section does not cite retired '--human-approval-gate'",
    "--human-approval-gate" not in SECTION,
)

if FAIL != 0:
    print("test-cli-naming-convention: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-cli-naming-convention: all checks passed.")
