#!/usr/bin/env python3
"""RABBIT-CAGE-BUG-92: stale spec invariants Inv 7 and Inv 14 removed.

Inv 7 referenced inline `rabbit-policy-start`/`rabbit-policy-end` markers
in CLAUDE.md that no longer exist (the @-import pointer form replaced the
inline block long ago). Inv 14 referenced `generate-skills-dir.py`, an
artifact that no longer exists (Inv 27 asserts its non-existence).

Both invariants document removed artifacts as if they still existed,
which violates the Designed Deprecation principle.

This regression test asserts:
(a) spec.md no longer carries the Inv 7 / Inv 14 paragraphs.
(b) sync-check.py source no longer carries the `_policy_section` helper or
    the rabbit-policy-start/end regex that scanned for the removed markers.
"""
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

SPEC_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


print("test-RABBIT-CAGE-BUG-92-stale-invariants-removed.py")
print()

with open(SPEC_MD) as f:
    spec = f.read()

# (a1) Inv 7 paragraph is absent. The Inv 7 paragraph was the line beginning
# `7. \`CLAUDE.md\` at repo root is a generated regular file ...` and naming
# the `rabbit-policy-start`/`rabbit-policy-end` inline section.
if re.search(r"(?m)^7\.\s+`CLAUDE\.md`.*rabbit-policy-start", spec):
    fail_t("spec.md still contains Inv 7 referencing rabbit-policy-start/end")
else:
    ok("spec.md no longer contains Inv 7 (rabbit-policy-start/end claim)")

# (a2) No surviving prose reference to the removed inline-marker section in
# the spec body (the spec must not document the markers as if they exist).
if "rabbit-policy-start" in spec or "rabbit-policy-end" in spec:
    fail_t("spec.md still mentions rabbit-policy-start / rabbit-policy-end")
else:
    ok("spec.md contains no rabbit-policy-start / rabbit-policy-end mention")

# (a3) Inv 14 paragraph is absent. Inv 14 was the `generate-skills-dir.py
# --check` paragraph. Inv 27 (which asserts the script does NOT exist) is
# the canonical statement and must remain.
if re.search(r"(?m)^14\.\s+`generate-skills-dir\.py", spec):
    fail_t("spec.md still contains Inv 14 referencing generate-skills-dir.py")
else:
    ok("spec.md no longer contains Inv 14 (generate-skills-dir.py claim)")

# (a4) Inv 27 (non-existence assertion) must remain — it is the canonical
# replacement and the only place the script name may appear.
if re.search(r"(?m)^27\.\s+`generate-skills-dir\.py`\s+does NOT exist", spec):
    ok("spec.md still contains Inv 27 (canonical non-existence assertion)")
else:
    fail_t("spec.md is missing Inv 27 (generate-skills-dir.py does NOT exist)")

# (b1) sync-check.py source no longer defines _policy_section.
with open(SYNC_CHECK) as f:
    sync = f.read()

if "_policy_section" in sync:
    fail_t("sync-check.py still references _policy_section helper")
else:
    ok("sync-check.py no longer defines or references _policy_section")

# (b2) sync-check.py source no longer matches on the removed markers.
if "rabbit-policy-start" in sync or "rabbit-policy-end" in sync:
    fail_t("sync-check.py still matches on rabbit-policy-start/end markers")
else:
    ok("sync-check.py no longer matches on rabbit-policy-start/end markers")

print()
if failures:
    print(f"FAIL: {failures}/{total} checks failed")
    sys.exit(1)
print(f"PASS: {total}/{total} checks passed")
