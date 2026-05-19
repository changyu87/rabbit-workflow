#!/usr/bin/env python3
# test-policy-invariants-v1-4-0.py — Verifies spec v1.4.0 invariants:
#   (1) philosophy.md, spec-rules.md, coding-rules.md exist and are non-empty.
#   (2) workflow-rules.md does NOT exist.
#   (3) No .sh files exist anywhere within the feature directory.
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


def check_no_sh_files():
    sh_files = []
    for root, _dirs, files in os.walk(FEATURE_DIR):
        for fname in files:
            if fname.endswith(".sh"):
                sh_files.append(os.path.join(root, fname))
    if sh_files:
        for f in sh_files:
            print(f"FAIL: .sh file found (Python is the sole scripting tech stack): {f}", file=sys.stderr)
        sys.exit(1)


# Invariant 1: three rule files exist and are non-empty
check_exists_nonempty("philosophy.md")
check_exists_nonempty("spec-rules.md")
check_exists_nonempty("coding-rules.md")

# Invariant 2: workflow-rules.md must NOT exist
check_absent("workflow-rules.md")

# Invariant 3: no .sh files anywhere in the feature directory
check_no_sh_files()

print("All checks passed.")
