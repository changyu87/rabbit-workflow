#!/usr/bin/env python3
"""test-contract-invokes.py — E2E for rabbit-housekeep's machine-readable
cross-feature INVOKE declarations.

Machine First (philosophy §1): every cross-feature reuse rabbit-housekeep
relies on MUST be declared in the structured JSON `invokes` block of
docs/contract.md, not in trailing prose only. This test parses the contract's
JSON block (the machine surface a consumer reads) and asserts each declared
INVOKE is real (the named skill/script exists on disk), with no behavior
described only in prose.

Asserts, against the real feature tree:

  t0: contract.md has a parseable JSON block with an `invokes` object.
  t1: the rabbit-decompose decomposition-shape reuse is declared as a
      machine-readable INVOKE under invokes.skills (Step 2 of the SKILL.md
      reuses rabbit-decompose's decomposition shape).
  t2: the rabbit-issue filing call is declared under invokes.scripts naming
      file-item.py, and the rabbit-auto-evolve record-decomposition.py call is
      declared under invokes.scripts.
  t3: every path declared under invokes.scripts resolves to a real file on
      disk (the declared INVOKE is real, not aspirational).
  t4: every skill declared under invokes.skills resolves to a real SKILL.md on
      disk under some .claude/features/*/skills/<name>/SKILL.md (the skill name
      need not match its owning feature's directory name).
  t5: the rabbit-decompose reuse is NOT prose-only — the trailing prose after
      the JSON block does not re-declare the decomposition-shape reuse as the
      sole carrier (it must appear in the machine block, asserted by t1).

Non-interactive. Exits non-zero on failure.

Version: 0.2.1
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
CONTRACT = os.path.join(FEATURE_DIR, "docs", "contract.md")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


with open(CONTRACT, encoding="utf-8") as f:
    contract_text = f.read()

# t0: parseable JSON block with invokes
m = re.search(r"```json\n(.*?)\n```", contract_text, re.DOTALL)
if not m:
    fail("t0", "no ```json block in contract.md")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)
try:
    doc = json.loads(m.group(1))
except json.JSONDecodeError as e:
    fail("t0", f"contract JSON block is not valid JSON: {e}")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)
invokes = doc.get("invokes")
if not isinstance(invokes, dict):
    fail("t0", "contract JSON has no `invokes` object")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "contract.md has a parseable JSON block with an invokes object")

inv_skills = invokes.get("skills", []) or []
inv_scripts = invokes.get("scripts", []) or []
skill_names = {s.get("name") for s in inv_skills if isinstance(s, dict)}
script_paths = [s.get("path") for s in inv_scripts if isinstance(s, dict)]

# t1: rabbit-decompose reuse declared as a machine-readable INVOKE
if "rabbit-decompose" in skill_names:
    ok("t1", "rabbit-decompose decomposition-shape reuse declared in "
             "invokes.skills")
else:
    fail("t1", "rabbit-decompose reuse not declared in invokes.skills "
               f"(skills={sorted(n for n in skill_names if n)})")

# t2: rabbit-issue file-item.py + rabbit-auto-evolve record-decomposition.py
has_file_item = any(
    p and p.endswith("rabbit-issue/scripts/file-item.py") for p in script_paths
)
has_record = any(
    p and p.endswith("rabbit-auto-evolve/scripts/record-decomposition.py")
    for p in script_paths
)
if has_file_item and has_record:
    ok("t2", "file-item.py and record-decomposition.py declared in "
             "invokes.scripts")
else:
    fail("t2", "missing structured INVOKE for filing/record-decomposition "
               f"(file_item={has_file_item}, record={has_record}, "
               f"paths={script_paths})")

# t3: every invokes.scripts path resolves to a real file
missing_scripts = [
    p for p in script_paths
    if not (p and os.path.isfile(os.path.join(REPO_ROOT, p)))
]
if not missing_scripts:
    ok("t3", "every invokes.scripts path resolves to a real file")
else:
    fail("t3", f"declared INVOKE scripts not found on disk: {missing_scripts}")

# t4: every invokes.skills name resolves to a real SKILL.md somewhere under
# .claude/features/*/skills/<name>/SKILL.md (skill name may differ from its
# owning feature's directory name).
features_root = os.path.join(REPO_ROOT, ".claude", "features")
missing_skills = []
for n in sorted(x for x in skill_names if x):
    found = False
    if os.path.isdir(features_root):
        for feat in os.listdir(features_root):
            candidate = os.path.join(
                features_root, feat, "skills", n, "SKILL.md"
            )
            if os.path.isfile(candidate):
                found = True
                break
    if not found:
        missing_skills.append(n)
if not missing_skills:
    ok("t4", "every invokes.skills name resolves to a real SKILL.md")
else:
    fail("t4", f"declared INVOKE skills not found on disk: {missing_skills}")

# t5: rabbit-decompose reuse not carried by prose alone — machine block is the
# carrier. Guard the regression by re-asserting the JSON declaration: prose may
# mention rabbit-decompose as the derived human view, but t1 must pass.
trailing = contract_text[m.end():]
if "rabbit-decompose" in trailing and "rabbit-decompose" not in skill_names:
    fail("t5", "rabbit-decompose reuse appears in trailing prose but NOT in "
               "the machine-readable invokes block (prose-only is the defect)")
else:
    ok("t5", "rabbit-decompose reuse is carried by the machine block, not "
             "prose-only")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
