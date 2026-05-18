#!/usr/bin/env python3
# test-rule-files-content.py — Spot-checks content of the three rule files.
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def check_phrase(file, phrase):
    path = os.path.join(FEATURE_DIR, file)
    with open(path) as f:
        content = f.read()
    if phrase not in content:
        print(f"FAIL: '{phrase}' not found in {path}", file=sys.stderr)
        sys.exit(1)


def check_phrase_absent(file, phrase):
    path = os.path.join(FEATURE_DIR, file)
    with open(path) as f:
        content = f.read()
    if phrase in content:
        print(f"FAIL: '{phrase}' should NOT be in {path} but was found", file=sys.stderr)
        sys.exit(1)


def check_first_heading(file, expected):
    path = os.path.join(FEATURE_DIR, file)
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                actual = line.rstrip("\n")
                if actual != expected:
                    print(
                        f"FAIL: first heading in {path} is '{actual}', expected '{expected}'",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                return
    print(f"FAIL: no heading found in {path}", file=sys.stderr)
    sys.exit(1)


# spec-rules.md
check_phrase("spec-rules.md", "Tool-Choice Tier")
check_phrase("spec-rules.md", "Schemas and Contracts")
check_phrase("spec-rules.md", "Lifecycle and Ownership")

# coding-rules.md
check_phrase("coding-rules.md", "Think Before Coding")
check_phrase("coding-rules.md", "Simplicity First")
check_phrase("coding-rules.md", "Karpathy")

# philosophy.md
check_phrase("philosophy.md", "Machine First")
check_phrase("philosophy.md", "Bounded Scope")
check_phrase("philosophy.md", "Designed Deprecation")

# CHANGE B — philosophy.md heading hierarchy fixed
# t_phil_h1: philosophy.md first non-empty line is "# Philosophy" (H1, not H2)
check_first_heading("philosophy.md", "# Philosophy")

# t_phil_no_h2: philosophy.md does NOT contain "## Philosophy" (the old H2)
check_phrase_absent("philosophy.md", "## Philosophy")

# t_phil_subsections: philosophy.md subsections use ## (H2), not ### (H3)
check_phrase("philosophy.md", "## 1. Machine First")

print("All checks passed.")
