#!/usr/bin/env python3
"""test-policy-invariants.py — Verifies policy spec invariants.

Covers:
  (1) philosophy.md, spec-rules.md, coding-rules.md exist and are non-empty.
  (2) workflow-rules.md does NOT exist.
  (3) No .sh files exist anywhere within the feature directory.
  (4) coding-rules.md Section 3 ("Surgical Changes") states that
      "uncommitted" includes BOTH staged and unstaged work from the current
      agent session.
  (5) Every Python file under test/ (excluding run.py) declares a
      `Deprecation criterion:` line in its module docstring (first ~30 lines).
  (7) test-policy-invariants.py is the canonical non-versioned name; no
      test-policy-invariants-v*.py exists; test-files-exist.py absent.
  (8) test-policy-bug-fixes.py docstring names a concrete observable
      retirement criterion (TICKETS_COVERED + Subsumes marker subsumption
      pointer); test-historical-fixes-retirement.py exists.
  (9) Test filename convention: no test/*.py uses the legacy ID-first forms
      test-POLICY-N-*.py, test-backlogNNN.py, or test-backlog-N-M.py.

Inv 6 (Read-before-Edit principle) is covered by test-rule-files-content.py.

Version: 1.1.0
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

# Invariant 4: coding-rules.md Section 3 ("Surgical Changes") clarifies that
# "uncommitted" includes BOTH staged and unstaged work from the current agent
# session.
coding_rules_path = os.path.join(FEATURE_DIR, "coding-rules.md")
with open(coding_rules_path) as f:
    coding_rules_text = f.read()
sec3_start = coding_rules_text.find("## 3. Surgical Changes")
if sec3_start < 0:
    print("FAIL: Inv 4: coding-rules.md missing '## 3. Surgical Changes' heading", file=sys.stderr)
    sys.exit(1)
sec3_end = coding_rules_text.find("\n## ", sec3_start + 1)
sec3 = coding_rules_text[sec3_start:sec3_end if sec3_end > 0 else len(coding_rules_text)]
sec3_lower = sec3.lower()
if "staged" not in sec3_lower:
    print("FAIL: Inv 4: Section 3 does not mention 'staged'", file=sys.stderr)
    sys.exit(1)
if "unstaged" not in sec3_lower:
    print("FAIL: Inv 4: Section 3 does not mention 'unstaged'", file=sys.stderr)
    sys.exit(1)
if not (
    "staged and unstaged" in sec3_lower
    or "staged or unstaged" in sec3_lower
    or "both staged" in sec3_lower
):
    print("FAIL: Inv 4: Section 3 does not clarify staged-and-unstaged equivalence", file=sys.stderr)
    sys.exit(1)

# Invariant 5: every test/*.py (except run.py) declares a `Deprecation criterion:`
# line in its module docstring (first ~30 lines).
missing_dc = []
for fname in sorted(os.listdir(TEST_DIR)):
    if fname == "run.py" or not fname.endswith(".py"):
        continue
    path = os.path.join(TEST_DIR, fname)
    with open(path) as f:
        head = "\n".join(f.read().splitlines()[:30])
    if "Deprecation criterion:" not in head:
        missing_dc.append(fname)
if missing_dc:
    for fname in missing_dc:
        print(f"FAIL: Inv 5: {fname} missing 'Deprecation criterion:' in module docstring (first 30 lines)", file=sys.stderr)
    sys.exit(1)

# Invariant 7: test-policy-invariants.py is canonical (non-versioned);
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

# Invariant 8: test-policy-bug-fixes.py docstring states a concrete observable
# retirement criterion, declares TICKETS_COVERED, and a retirement-watch test
# exists.
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

# Invariant 9: no test/*.py file uses the legacy ID-first filename forms.
# Behavior-first names only; ticket IDs go in docstring headers as `Traces:`
# lines. run.py is the harness, not a test, and is excluded.
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
