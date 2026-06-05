#!/usr/bin/env python3
"""test-native-workflow-decision-doc.py — native-Workflow coexistence decision.

End-to-end test that the native-Workflow research deliverable — contract's
decision record on Claude Code's native Workflow framework — exists as a
governed artifact under docs/decisions/, carries the required lifecycle
metadata for its artifact type, and contains the three explicitly-requested
deliverable sections:

  t1  the decision doc exists at docs/decisions/native-workflow-coexistence.md.
  t2  it carries YAML frontmatter delimited by '---' lines.
  t3  frontmatter declares feature: contract plus owner and
      deprecation_criterion (lifecycle metadata for a contract-owned doc).
  t4  the body contains a primitive-by-primitive mapping section (Claude Code
      Workflow primitive -> rabbit concept) — asserted via a markdown table
      header naming both sides.
  t5  the body records the recommendation and it is HYBRID / COEXIST.
  t6  the body names a way IN (adoption trigger) and a way OUT (off-ramp /
      rollback).
  t7  the body carries no bare '#NNN' historical-burden tombstone: issue and
      PR numbers belong in CHANGELOG/commit/PR, not in a gated doc surface.
      (The decision text MAY name the issue in prose without the '#' tag.)

Non-interactive. Exits non-zero on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the native-Workflow coexistence decision is
superseded by a contract feature-touch adopting a native governance-tier
mechanism — at which point this doc and its test fold into that touch.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
DOC = os.path.join(FEATURE_DIR, "docs", "decisions",
                   "native-workflow-coexistence.md")

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


if not os.path.isfile(DOC):
    ko("t1", f"missing decision doc: {DOC}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t1", "decision doc exists")

with open(DOC, encoding="utf-8") as f:
    text = f.read()

fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
if not fm_match:
    ko("t2", "no YAML frontmatter delimited by --- lines at top of file")
    fm = ""
    body = text
else:
    ok("t2", "YAML frontmatter present")
    fm = fm_match.group(1)
    body = text[fm_match.end():]

# t3: lifecycle metadata.
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

# t4: primitive-by-primitive mapping. Require a markdown table whose header
# row names both the native Workflow side and the rabbit side.
mapping = re.search(
    r"\|[^\n]*[Ww]orkflow[^\n]*\|[^\n]*[Rr]abbit[^\n]*\|",
    body,
)
if mapping:
    ok("t4", "primitive-by-primitive mapping table present")
else:
    ko("t4", "no mapping table header naming both Workflow and rabbit sides")

# t5: recommendation is HYBRID / COEXIST.
rec = re.search(r"##\s*Recommendation", body, re.IGNORECASE)
hybrid = re.search(r"\b(hybrid|coexist)\b", body, re.IGNORECASE)
if rec and hybrid:
    ok("t5", "recommendation section records HYBRID/COEXIST")
else:
    ko("t5", f"recommendation section / verdict missing "
             f"(section={bool(rec)}, hybrid/coexist={bool(hybrid)})")

# t6: way in AND way out.
way_in = re.search(r"way\s+in", body, re.IGNORECASE)
way_out = re.search(r"way\s+out|off-?ramp|rollback", body, re.IGNORECASE)
if way_in and way_out:
    ok("t6", "way IN (adoption trigger) and way OUT (off-ramp) both present")
else:
    ko("t6", f"missing way in/out (in={bool(way_in)}, out={bool(way_out)})")

# t7: no bare '#NNN' historical tombstone in the doc body.
hits = re.findall(r"#\d+", body)
if hits:
    ko("t7", f"bare #NNN tombstone(s) in doc body: {sorted(set(hits))} "
             "(cite issues in CHANGELOG/commit/PR, not the doc surface)")
else:
    ok("t7", "no bare #NNN tombstone in doc body")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
