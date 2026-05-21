#!/usr/bin/env python3
"""test-changelog-exists.py — Inv 39 / CONTRACT-BACKLOG-30.

End-to-end test that .claude/features/contract/CHANGELOG.md exists and is
structurally well-formed:

  t1  file exists.
  t2  carries YAML frontmatter delimited by '---' lines.
  t3  frontmatter declares feature: contract, owner, deprecation_criterion.
  t4  body lists at least one tombstone entry for each of the 7 originally
      retired invariants (Inv 2, 6, 8, 14, 27, 29, 31).

Non-interactive. Exits non-zero on any failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
CHANGELOG = os.path.join(FEATURE_DIR, "CHANGELOG.md")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


if not os.path.isfile(CHANGELOG):
    ko("t1", f"missing: {CHANGELOG}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t1", "CHANGELOG.md exists")

with open(CHANGELOG, encoding="utf-8") as f:
    text = f.read()

# t2: frontmatter
fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
if not fm_match:
    ko("t2", "no YAML frontmatter delimited by --- lines at top of file")
else:
    ok("t2", "YAML frontmatter present")
    fm = fm_match.group(1)
    # t3: required keys
    required = ["feature:", "owner:", "deprecation_criterion:"]
    missing = [k for k in required if k not in fm]
    if missing:
        ko("t3a", f"frontmatter missing keys: {missing}")
    else:
        ok("t3a", "frontmatter has feature/owner/deprecation_criterion")
    if re.search(r"^feature:\s*contract\s*$", fm, re.MULTILINE):
        ok("t3b", "frontmatter declares feature: contract")
    else:
        ko("t3b", f"frontmatter does not declare 'feature: contract'; got:\n{fm}")

# t4: tombstone presence for the 7 retired invariants
RETIRED_NUMS = [2, 6, 8, 14, 27, 29, 31]
body = text[fm_match.end():] if fm_match else text
missing_entries = []
for n in RETIRED_NUMS:
    # Accept "Inv 2", "Inv 2 —", "Inv 2.", "### Inv 2", etc. as evidence.
    if not re.search(rf"\bInv\s+{n}\b", body):
        missing_entries.append(n)
if missing_entries:
    ko("t4", f"CHANGELOG body missing tombstones for: {missing_entries}")
else:
    ok("t4", f"all retired invariants ({RETIRED_NUMS}) have tombstones in body")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
