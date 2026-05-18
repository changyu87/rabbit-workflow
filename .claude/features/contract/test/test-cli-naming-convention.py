#!/usr/bin/env python3
# test-cli-naming-convention.py — assert spec declares CLI naming convention
# (Inv 15: boolean values use true/false exclusively; Inv 16: positive-streamlined names).
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

# Locate invariant 15 — a numbered list item starting with "15." in the In Scope list.
inv15_match = re.search(r"^15\.\s+(.+?)(?=^\d+\.\s|\Z)", SPEC, re.DOTALL | re.MULTILINE)
check("spec contains invariant 15", inv15_match is not None)
INV15 = inv15_match.group(1) if inv15_match else ""

# Locate invariant 16.
inv16_match = re.search(r"^16\.\s+(.+?)(?=^\d+\.\s|\Z|^##)", SPEC, re.DOTALL | re.MULTILINE)
check("spec contains invariant 16", inv16_match is not None)
INV16 = inv16_match.group(1) if inv16_match else ""

# Inv 15 text — must mention true and false as the canonical boolean values,
# and prohibit at least `enabled`/`disabled`.
check("Inv 15 mentions 'true'", "true" in INV15)
check("Inv 15 mentions 'false'", "false" in INV15)
check("Inv 15 prohibits 'enabled'", "enabled" in INV15)
check("Inv 15 prohibits 'disabled'", "disabled" in INV15)

# Inv 16 text — must prohibit each negating prefix.
check("Inv 16 prohibits 'no-' prefix", "no-" in INV16)
check("Inv 16 prohibits 'disable-' prefix", "disable-" in INV16)
check("Inv 16 prohibits 'skip-' prefix", "skip-" in INV16)
check("Inv 16 prohibits 'without-' prefix", "without-" in INV16)

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

if FAIL != 0:
    print("test-cli-naming-convention: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-cli-naming-convention: all checks passed.")
