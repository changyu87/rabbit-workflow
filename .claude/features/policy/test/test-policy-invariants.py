#!/usr/bin/env python3
"""test-policy-invariants.py — Verifies policy spec invariants.

Covers:
  (1) philosophy.md, spec-rules.md, coding-rules.md exist and are non-empty.
  (2) workflow-rules.md does NOT exist.
  (3) No .sh files exist anywhere within the feature directory.
  (5) test-coding-rules-numbering.py (post-BACKLOG-14 rename) carries an EOL
      header naming its retirement criterion.
  (7) test-policy-invariants.py is the canonical non-versioned name; no
      test-policy-invariants-v1-*.py exists; test-files-exist.py absent.
  (8) test-policy-bug-fixes.py docstring names a concrete observable
      retirement criterion (TICKETS_COVERED + Subsumes marker subsumption
      pointer); test-historical-fixes-retirement.py exists.
  (9) Test filename convention: no test/*.py uses the legacy ID-first forms
      test-POLICY-N-*.py, test-backlogNNN.py, or test-backlog-N-M.py.

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when this spec-conformance suite merges into a
broader cross-feature invariants harness.
"""
import glob
import os
import re
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

# Invariant 5 (BACKLOG-11, rename BACKLOG-14): test-coding-rules-numbering.py
# MUST exist (renamed from test-backlog003.py) and carry an EOL retirement
# criterion in its header.
numbering_test = os.path.join(TEST_DIR, "test-coding-rules-numbering.py")
if not os.path.isfile(numbering_test):
    print(f"FAIL: Inv 5: test-coding-rules-numbering.py not found: {numbering_test}", file=sys.stderr)
    sys.exit(1)
with open(numbering_test) as f:
    numbering_head = "\n".join(f.read().splitlines()[:30])
if "retired" not in numbering_head.lower() and "retirement" not in numbering_head.lower() and "end-of-life" not in numbering_head.lower():
    print(f"FAIL: Inv 5: test-coding-rules-numbering.py header lacks an EOL/retirement criterion", file=sys.stderr)
    sys.exit(1)

# Invariant 8 (BACKLOG-14, F5): test-policy-bug-fixes.py docstring states a
# concrete observable retirement criterion, declares TICKETS_COVERED, and a
# retirement-watch test exists.
bug_fixes_path = os.path.join(TEST_DIR, "test-policy-bug-fixes.py")
if not os.path.isfile(bug_fixes_path):
    print(f"FAIL: Inv 8: test-policy-bug-fixes.py not found", file=sys.stderr)
    sys.exit(1)
with open(bug_fixes_path) as f:
    bug_fixes_text = f.read()
if "TICKETS_COVERED" not in bug_fixes_text:
    print(f"FAIL: Inv 8: test-policy-bug-fixes.py missing TICKETS_COVERED constant", file=sys.stderr)
    sys.exit(1)
if "Subsumes" not in bug_fixes_text:
    print(f"FAIL: Inv 8: test-policy-bug-fixes.py docstring does not name the Subsumes-marker retirement pointer", file=sys.stderr)
    sys.exit(1)
watch_test = os.path.join(TEST_DIR, "test-historical-fixes-retirement.py")
if not os.path.isfile(watch_test):
    print(f"FAIL: Inv 8: test-historical-fixes-retirement.py not found", file=sys.stderr)
    sys.exit(1)

# Invariant 9 (BACKLOG-14, F6): no test/*.py file uses the legacy ID-first
# filename forms. Behavior-first names only; ticket IDs go in docstring headers
# as `Traces: POLICY-...` lines. run.py is the harness, not a test, and is
# excluded.
LEGACY_FORMS = [
    re.compile(r"^test-POLICY-\d+-.*\.py$"),
    re.compile(r"^test-backlog\d+\.py$"),
    re.compile(r"^test-backlog-\d+-\d+\.py$"),
]
offenders = []
for fname in sorted(os.listdir(TEST_DIR)):
    if fname == "run.py" or not fname.endswith(".py"):
        continue
    for pat in LEGACY_FORMS:
        if pat.match(fname):
            offenders.append(fname)
            break
if offenders:
    for o in offenders:
        print(f"FAIL: Inv 9: legacy ID-first test filename forbidden: {o}", file=sys.stderr)
    sys.exit(1)

print("All checks passed.")
