#!/usr/bin/env python3
# test-policy-invariants-v1-2-0.py — Verifies spec v1.2.0 invariants:
#   (1) philosophy.md, spec-rules.md, coding-rules.md exist and are non-empty.
#   (2) workflow-rules.md does NOT exist.
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def check_exists_nonempty(rel):
    path = os.path.join(FEATURE_DIR, rel)
    if not os.path.isfile(path):
        print(f"FAIL: missing file: {path}", file=sys.stderr)
        sys.exit(1)
    if os.path.getsize(path) == 0:
        print(f"FAIL: empty file: {path}", file=sys.stderr)
        sys.exit(1)


def check_absent(rel):
    path = os.path.join(FEATURE_DIR, rel)
    if os.path.isfile(path):
        print(f"FAIL: file must not exist: {path}", file=sys.stderr)
        sys.exit(1)


# Invariant 1: three rule files exist and are non-empty
check_exists_nonempty("philosophy.md")
check_exists_nonempty("spec-rules.md")
check_exists_nonempty("coding-rules.md")

# Invariant 2: workflow-rules.md must NOT exist
check_absent("workflow-rules.md")

print("All checks passed.")
