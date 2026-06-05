#!/usr/bin/env python3
"""test-dispatch-journal-research-doc.py — journal/resume research deliverable.

End-to-end test that the journal/resume research deliverable — tdd-subagent's
findings doc on whether the TDD dispatch can adopt a journal/resume
mechanism — exists as a governed artifact under docs/research/, carries the
required lifecycle metadata for its artifact type, and contains the
explicitly-requested deliverable sections:

  t1  the research doc exists at docs/research/dispatch-journal-resume.md.
  t2  it carries YAML frontmatter delimited by '---' lines.
  t3  frontmatter declares feature: tdd-subagent plus owner and
      deprecation_criterion (lifecycle metadata for a tdd-subagent-owned doc).
  t4  the body records a clear CAN or CANNOT verdict (a Verdict section whose
      text names one of CAN / CANNOT).
  t5  the body grounds the analysis in today's recovery machinery — it names
      the state fields the spike was told to investigate: in_flight and
      pending_post_merge.
  t6  the body names a way IN (adoption trigger) and a way OUT (off-ramp /
      rollback).
  t7  the body carries no bare '#NNN' historical-burden tombstone: issue and
      PR numbers belong in CHANGELOG/commit/PR, not in a gated doc surface.
      (The decision text MAY name issues in prose without the '#' tag.)

Non-interactive. Exits non-zero on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (tdd-subagent)
Deprecation criterion: when the dispatch-journal research deliverable is
superseded by the journal implementation folding this record into its
CHANGELOG — at which point this doc and its test fold into that touch.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
DOC = os.path.join(FEATURE_DIR, "docs", "research",
                   "dispatch-journal-resume.md")

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
    ko("t1", f"missing research doc: {DOC}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t1", "research doc exists")

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
if re.search(r"^feature:\s*tdd-subagent\s*$", fm, re.MULTILINE):
    ok("t3b", "frontmatter declares feature: tdd-subagent")
else:
    ko("t3b", f"frontmatter does not declare 'feature: tdd-subagent'; got:\n{fm}")

# t4: a clear CAN or CANNOT verdict.
verdict_section = re.search(r"##\s*Verdict", body, re.IGNORECASE)
verdict_word = re.search(r"\b(CANNOT|CAN)\b", body)
if verdict_section and verdict_word:
    ok("t4", f"verdict section records a clear {verdict_word.group(1)} verdict")
else:
    ko("t4", f"verdict missing (section={bool(verdict_section)}, "
             f"CAN/CANNOT word={bool(verdict_word)})")

# t5: grounded in today's recovery machinery — names in_flight and
# pending_post_merge (the fields the spike was told to investigate).
grounded = "in_flight" in body and "pending_post_merge" in body
if grounded:
    ok("t5", "body grounds analysis in in_flight + pending_post_merge")
else:
    ko("t5", f"body does not name the investigated state fields "
             f"(in_flight={'in_flight' in body}, "
             f"pending_post_merge={'pending_post_merge' in body})")

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
