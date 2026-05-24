#!/usr/bin/env python3
"""test-policy-bug-fixes.py — documentary regression guard for closed
historical policy tickets.

Role: a single kitchen-sink suite that re-asserts the structural fixes of 9
closed tickets so they cannot silently regress. It is NOT the canonical home
for these checks — `test-policy-invariants.py` is. This file exists only until
each assertion is folded into the invariants suite.

TICKETS_COVERED lists every historical ticket this file currently guards. The
companion watch test (`test-historical-fixes-retirement.py`) parses this list,
scans `test-policy-invariants.py` for `# Subsumes: <ticket-id>` marker
comments, and FAILS when every ticket is subsumed — that failure is the
explicit signal that this file (and the watch test) MUST be deleted together.
The previous open-ended criterion ('when each bug/backlog has its own
targeted test or is closed') is REMOVED — it never fired because the tickets
are already closed.

Traces: POLICY-BUG-2, POLICY-BUG-7, POLICY-BUG-18, POLICY-BUG-19,
        POLICY-BACKLOG-1, POLICY-BACKLOG-2, POLICY-BACKLOG-5,
        POLICY-BACKLOG-6, POLICY-BACKLOG-9. Retirement scaffolding added under
        POLICY-BACKLOG-14. POLICY-BUG-9 dropped under POLICY-BACKLOG-15:
        the file it guarded (test-no-stale-imports.py) moved to rabbit-cage.

Version: 2.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: delete this file (and test-historical-fixes-retirement.py)
once `test-policy-invariants.py` carries a `# Subsumes: <ticket-id>` marker
comment for every ticket in TICKETS_COVERED below.
"""

import json
import os
import re
import sys

# Module-level constant consumed by test-historical-fixes-retirement.py.
# Keep names exactly as filed (one per ticket; no aliases).
TICKETS_COVERED = [
    "POLICY-BUG-2",
    "POLICY-BUG-7",
    "POLICY-BUG-18",
    "POLICY-BUG-19",
    "POLICY-BACKLOG-1",
    "POLICY-BACKLOG-2",
    "POLICY-BACKLOG-5",
    "POLICY-BACKLOG-6",
    "POLICY-BACKLOG-9",
]

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


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
