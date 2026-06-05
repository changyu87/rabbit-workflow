#!/usr/bin/env python3
"""test-deprecation-criterion-governance-scoped.py

End-to-end test that the contract feature's OWN deprecation_criterion is scoped
to its GOVERNANCE surface, not to the mere existence of a native
orchestration/workflow primitive.

Background: Claude Code now ships a native Workflow orchestration tool. That
covers the orchestration tier only; contract's reason to exist is its
governance surface (the cross-feature contract gate, version lockstep,
invariant numbering, schema/template ownership). The deprecation_criterion must
therefore NOT read as a blanket "native workflow mechanism exists -> deprecate"
trigger; it must require a native mechanism that supersedes the GOVERNANCE
surface specifically.

This test reads the criterion from every location where the contract feature
declares its own deprecation_criterion (feature.json + docs/spec.md
frontmatter) and asserts:

  t1  feature.json deprecation_criterion is present and governance-scoped.
  t2  docs/spec.md frontmatter deprecation_criterion is present and
      governance-scoped.
  t3  the two declarations agree on the governance scoping (lockstep
      consistency): neither reads as a blanket orchestration/workflow-existence
      trigger.

"Governance-scoped" means the text mentions the word "governance" AND names at
least one concrete governance element (contract gate, version lockstep,
invariant numbering, or schema/template ownership), AND does NOT read as the
bare blanket trigger.

Non-interactive. Exits non-zero on any failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec.md")

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


# The blanket trigger we must NOT match: a bare "native workflow contract
# mechanism" / "native workflow mechanism" with no governance scoping.
BLANKET_RE = re.compile(
    r"native\s+workflow\s+(contract\s+)?mechanism\s*$",
    re.IGNORECASE,
)

# Concrete governance elements; at least one must be named.
GOVERNANCE_ELEMENTS = [
    r"contract\s+gate",
    r"version[\s-]lockstep|lockstep",
    r"invariant\s+number",
    r"schema/template",
]


def is_governance_scoped(text):
    """Return (bool, reason)."""
    low = text.strip()
    if BLANKET_RE.search(low):
        return False, "reads as the blanket native-workflow-exists trigger"
    if "governance" not in low.lower():
        return False, "does not mention 'governance'"
    if not any(re.search(p, low, re.IGNORECASE) for p in GOVERNANCE_ELEMENTS):
        return False, "names no concrete governance element"
    return True, "governance-scoped"


def read_feature_json_criterion():
    import json
    with open(FEATURE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("deprecation_criterion")


def read_spec_frontmatter_criterion():
    with open(SPEC_MD, encoding="utf-8") as f:
        text = f.read()
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm:
        return None
    m = re.search(r"^deprecation_criterion:\s*(.+?)\s*$", fm.group(1),
                  re.MULTILINE)
    return m.group(1) if m else None


# t1: feature.json
fj = read_feature_json_criterion()
if not fj:
    ko("t1", "feature.json has no deprecation_criterion")
else:
    scoped, reason = is_governance_scoped(fj)
    if scoped:
        ok("t1", f"feature.json governance-scoped: {fj!r}")
    else:
        ko("t1", f"feature.json not governance-scoped ({reason}): {fj!r}")

# t2: docs/spec.md frontmatter
sm = read_spec_frontmatter_criterion()
if not sm:
    ko("t2", "docs/spec.md frontmatter has no deprecation_criterion")
else:
    scoped, reason = is_governance_scoped(sm)
    if scoped:
        ok("t2", f"spec.md governance-scoped: {sm!r}")
    else:
        ko("t2", f"spec.md not governance-scoped ({reason}): {sm!r}")

# t3: lockstep consistency — neither declaration a blanket trigger.
if fj and sm:
    if not BLANKET_RE.search(fj) and not BLANKET_RE.search(sm):
        ok("t3", "neither declaration reads as the blanket trigger")
    else:
        ko("t3", "a declaration still reads as the blanket trigger")
else:
    ko("t3", "missing a declaration; cannot check lockstep consistency")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
