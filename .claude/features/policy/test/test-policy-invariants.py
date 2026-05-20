#!/usr/bin/env python3
"""test-policy-invariants.py — Verifies policy spec invariants.

Covers:
  (1) philosophy.md, spec-rules.md, coding-rules.md exist and are non-empty.
  (2) workflow-rules.md does NOT exist.
  (3) No .sh files exist anywhere within the feature directory.
  (7) test-policy-invariants.py is the canonical non-versioned name; no
      test-policy-invariants-v1-*.py exists; test-files-exist.py absent.

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when this spec-conformance suite merges into a
broader cross-feature invariants harness.
"""
import glob
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DIR = os.path.join(FEATURE_DIR, "test")


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

# Invariant 7 (BACKLOG-13): test-policy-invariants.py is canonical (non-versioned);
# the legacy versioned form MUST NOT exist; test-files-exist.py MUST NOT exist.
canonical = os.path.join(TEST_DIR, "test-policy-invariants.py")
if not os.path.isfile(canonical):
    print(f"FAIL: canonical test name not found: {canonical}", file=sys.stderr)
    sys.exit(1)
versioned = glob.glob(os.path.join(TEST_DIR, "test-policy-invariants-v*.py"))
if versioned:
    for v in versioned:
        print(f"FAIL: legacy versioned test name forbidden: {v}", file=sys.stderr)
    sys.exit(1)
files_exist_legacy = os.path.join(TEST_DIR, "test-files-exist.py")
if os.path.isfile(files_exist_legacy):
    print(f"FAIL: test-files-exist.py must not exist (subsumed): {files_exist_legacy}", file=sys.stderr)
    sys.exit(1)

print("All checks passed.")
