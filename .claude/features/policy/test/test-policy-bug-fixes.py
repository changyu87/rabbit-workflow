#!/usr/bin/env python3
"""test-policy-bug-fixes.py — assertions for the policy bug/backlog cleanup cycle.

Covers:
  POLICY-BUG-1   test-backlog003.py rule count assertion matches actual 4 rules
  POLICY-BUG-2   test-rule-files-content.py comment says 'three rule files'
  POLICY-BUG-7   spec.md and contract.md version are aligned
  POLICY-BUG-19  feature.json, spec.md, and contract.md versions all align (three-way)
  POLICY-BUG-9   test-POLICY-1 t2 comment correctly describes the @-import regex
  POLICY-BUG-18  test-policy-invariants-v1-2-0.py is removed from run.py (or deleted)
  POLICY-BACKLOG-1  coding-rules.md has a 'do not create docs unless asked' rule
  POLICY-BACKLOG-2  spec/coding-rules.md specifies WHERE owner/version/deprecation_criterion lives
  POLICY-BACKLOG-5  coding-rules.md has an 'avoid emojis unless asked' rule
  POLICY-BACKLOG-6  coding-rules.md references TDD discipline
  POLICY-BACKLOG-9  philosophy.md Bounded Scope references contract.md schema

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when each bug/backlog has its own targeted test or is closed.
"""

import json
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


# POLICY-BUG-1: test-backlog003.py rule count assertion matches actual count.
# Originally said 'rules stop at 5' but only 4 rules existed. This cycle added a
# fifth rule (Output Hygiene), so the assertion is now correct in its claim that
# no sixth rule exists.
b003_path = os.path.join(FEATURE_DIR, "test", "test-backlog003.py")
with open(b003_path) as f:
    b003 = f.read()
# Count actual top-level '## N.' rules in coding-rules.md.
coding_path = os.path.join(FEATURE_DIR, "coding-rules.md")
with open(coding_path) as f:
    coding_text = f.read()
rule_headings = re.findall(r'^## (\d+)\.', coding_text, re.MULTILINE)
rule_count = len(rule_headings)
# The test must assert the next-after-last heading is absent.
expected_phrase = f"rules stop at {rule_count}"
if expected_phrase in b003:
    ok(f"POLICY-BUG-1: test-backlog003.py asserts '{expected_phrase}' matching {rule_count} actual rules")
else:
    ko(f"POLICY-BUG-1: test-backlog003.py rule-count phrase does not match actual ({rule_count} rules)")


# POLICY-BUG-2: test-rule-files-content.py comment says 'three' rule files
rfc_path = os.path.join(FEATURE_DIR, "test", "test-rule-files-content.py")
with open(rfc_path) as f:
    rfc = f.read()
if "four rule files" in rfc:
    ko("POLICY-BUG-2: test-rule-files-content.py comment still says 'four rule files'")
elif "three rule files" in rfc:
    ok("POLICY-BUG-2: test-rule-files-content.py comment says 'three rule files'")
else:
    ko("POLICY-BUG-2: test-rule-files-content.py comment missing rule-count phrase")


# POLICY-BUG-7: spec.md and contract.md versions match
spec_path = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
contract_path = os.path.join(FEATURE_DIR, "docs", "spec", "contract.md")
with open(spec_path) as f:
    spec_text = f.read()
with open(contract_path) as f:
    contract_text = f.read()


def header_version(text):
    m = re.search(r'^version:\s*([0-9]+\.[0-9]+\.[0-9]+)', text, re.MULTILINE)
    return m.group(1) if m else None


spec_v = header_version(spec_text)
contract_v = header_version(contract_text)
if spec_v and contract_v and spec_v == contract_v:
    ok(f"POLICY-BUG-7: spec.md and contract.md aligned at {spec_v}")
else:
    ko(f"POLICY-BUG-7: spec.md v={spec_v} != contract.md v={contract_v}")


# POLICY-BUG-19: feature.json, spec.md, and contract.md versions all match (three-way alignment)
feature_json_path = os.path.join(FEATURE_DIR, "feature.json")
with open(feature_json_path) as f:
    feature_json = json.load(f)
feature_v = feature_json.get("version")
if spec_v and contract_v and feature_v and spec_v == contract_v == feature_v:
    ok(f"POLICY-BUG-19: feature.json, spec.md, contract.md all aligned at {feature_v}")
else:
    ko(f"POLICY-BUG-19: three-way mismatch — feature.json={feature_v}, spec.md={spec_v}, contract.md={contract_v}")


# POLICY-BUG-9: t2 comment correctly describes the @-import regex format
p1_path = os.path.join(FEATURE_DIR, "test", "test-POLICY-1-no-stale-imports.py")
with open(p1_path) as f:
    p1 = f.read()
# The actual regex used in test-imports-resolve.py is r'^(@[^\s]+)' — no '@./...' form.
t2_block_start = p1.find("# t2:")
t2_block_end = p1.find("\nIMPORTS_TEST", t2_block_start)
t2_block = p1[t2_block_start:t2_block_end] if t2_block_start != -1 else ""
if "'@./" in t2_block or "regex '^@\\./" in t2_block:
    ko("POLICY-BUG-9: t2 comment still references the wrong regex form")
else:
    ok("POLICY-BUG-9: t2 comment no longer claims the regex is '^@\\./...'")


# POLICY-BUG-18: test-policy-invariants-v1-2-0.py not invoked by run.py (or file deleted)
runpy_path = os.path.join(FEATURE_DIR, "test", "run.py")
with open(runpy_path) as f:
    runpy_text = f.read()
# Look only for an active invocation (run_test("..."))
if re.search(r'^\s*run_test\(["\']test-policy-invariants-v1-2-0\.py["\']', runpy_text, re.MULTILINE):
    ko("POLICY-BUG-18: run.py still invokes superseded test-policy-invariants-v1-2-0.py")
else:
    ok("POLICY-BUG-18: run.py no longer invokes test-policy-invariants-v1-2-0.py")


# POLICY-BACKLOG-1: 'do not create docs unless asked' rule in coding-rules.md
coding_path = os.path.join(FEATURE_DIR, "coding-rules.md")
with open(coding_path) as f:
    coding = f.read()
if re.search(r"(?i)(documentation|docs|markdown).{0,80}(unless|without|only).{0,30}(ask|request)", coding, re.DOTALL):
    ok("POLICY-BACKLOG-1: coding-rules.md has a 'no unsolicited docs' rule")
else:
    ko("POLICY-BACKLOG-1: coding-rules.md missing 'no unsolicited docs' rule")


# POLICY-BACKLOG-2: spec-rules.md specifies WHERE owner/version/deprecation_criterion lives
spec_rules_path = os.path.join(FEATURE_DIR, "spec-rules.md")
with open(spec_rules_path) as f:
    spec_rules = f.read()
if "feature.json" in spec_rules or re.search(r"frontmatter", spec_rules, re.IGNORECASE):
    ok("POLICY-BACKLOG-2: spec-rules.md specifies the metadata location")
else:
    ko("POLICY-BACKLOG-2: spec-rules.md does not specify WHERE metadata lives")


# POLICY-BACKLOG-5: 'avoid emojis unless asked' rule in coding-rules.md
if re.search(r"(?i)emoji", coding):
    ok("POLICY-BACKLOG-5: coding-rules.md mentions emoji policy")
else:
    ko("POLICY-BACKLOG-5: coding-rules.md missing emoji policy")


# POLICY-BACKLOG-6: coding-rules.md references TDD discipline
if re.search(r"\bTDD\b", coding):
    ok("POLICY-BACKLOG-6: coding-rules.md references TDD")
else:
    ko("POLICY-BACKLOG-6: coding-rules.md does not reference TDD")


# POLICY-BACKLOG-9: philosophy.md Bounded Scope references contract.md schema
phil_path = os.path.join(FEATURE_DIR, "philosophy.md")
with open(phil_path) as f:
    phil = f.read()
bs_idx = phil.find("Bounded Scope")
dd_idx = phil.find("Designed Deprecation")
if bs_idx != -1:
    bs_section = phil[bs_idx:dd_idx if dd_idx > bs_idx else len(phil)]
    if "contract.md" in bs_section:
        ok("POLICY-BACKLOG-9: philosophy.md Bounded Scope references contract.md")
    else:
        ko("POLICY-BACKLOG-9: philosophy.md Bounded Scope does not reference contract.md")
else:
    ko("POLICY-BACKLOG-9: 'Bounded Scope' section not found")


if FAIL:
    print("\ntest-policy-bug-fixes: FAIL", file=sys.stderr)
    sys.exit(1)
print("\ntest-policy-bug-fixes: all checks passed.")
