#!/usr/bin/env python3
# test-files-exist.py — Verifies all required policy files exist and are non-empty.
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def check_file(rel):
    path = os.path.join(FEATURE_DIR, rel)
    if not os.path.isfile(path):
        print(f"FAIL: missing file: {path}", file=sys.stderr)
        sys.exit(1)
    if os.path.getsize(path) == 0:
        print(f"FAIL: empty file: {path}", file=sys.stderr)
        sys.exit(1)


check_file("philosophy.md")
check_file("spec-rules.md")
check_file("coding-rules.md")
check_file("docs/spec/spec.md")
check_file("docs/spec/contract.md")
