#!/usr/bin/env python3
"""E2E tests for rabbit-spec Wave 4 bug/backlog closures.

Covers:
  BUG-4   contract.md 'Consumed By' / 'Does NOT Invoke' are process-agnostic
  BUG-8   SKILL.md Step 1 clarifies "examples include; MAY read any file"
  BUG-9   SKILL.md and spec.md mention docs/spec/contract.md as read target
  BUG-10  SKILL.md "What You Do NOT Do" doesn't forbid Step 3 superpowers
  BACKLOG-1 impl-suggestion schema documents optional owner/deprecation fields
  BACKLOG-2 build-contract.json registers rabbit-spec SKILL.md
  BACKLOG-3 generated_at format spec'd as ISO 8601 UTC
  BACKLOG-4 affected_files semantics clarified in spec and SKILL.md
  BACKLOG-5 SKILL.md documents args format
  BACKLOG-6 SKILL.md describes graceful error for non-existent feature-name
  BACKLOG-7 feature.json `updated` date present (manual maintenance)
  BACKLOG-8 spec.md Out of Scope no longer hard-names the TDD subagent
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
CONTRACT_MD = os.path.join(FEATURE_DIR, "docs", "spec", "contract.md")
SKILL_MD = os.path.join(FEATURE_DIR, "skills", "rabbit-spec", "SKILL.md")
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")
BUILT_SKILL = os.path.join(REPO_ROOT, ".claude", "skills", "rabbit-spec", "SKILL.md")
BUILD_CONTRACT = os.path.join(REPO_ROOT, ".claude", "features", "contract", "build-contract.json")


def _read(p):
    with open(p) as f:
        return f.read()


def _section(text, heading):
    m = re.search(rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# BUG-4: contract.md 'Consumed By' MUST NOT name a single specific consumer
# (process-agnostic Inv 7). Same for 'Does NOT Invoke': must not encode
# process-specific exclusions.
# ---------------------------------------------------------------------------
def test_bug4_contract_consumed_by_is_generic():
    text = _read(CONTRACT_MD)
    consumed = _section(text, "Consumed By")
    assert consumed is not None, "contract.md must have 'Consumed By' section"
    lowered = consumed.lower()
    # The contract must not state rabbit-feature-touch as the sole consumer.
    # Generic phrasing ("any process that...") is required.
    assert "rabbit-feature-touch" not in lowered, \
        "Consumed By must not single out rabbit-feature-touch as sole consumer"


def test_bug4_contract_does_not_invoke_is_generic():
    text = _read(CONTRACT_MD)
    section = _section(text, "Does NOT Invoke")
    assert section is not None, "contract.md must have 'Does NOT Invoke' section"
    lowered = section.lower()
    assert "rabbit-feature-touch" not in lowered, \
        "Does NOT Invoke must not enumerate specific caller names"


# ---------------------------------------------------------------------------
# BUG-8: SKILL.md Step 1 must clarify the listed read targets are examples,
# not an exhaustive list. The skill MAY read any file in the feature dir
# (Inv 4).
# ---------------------------------------------------------------------------
def test_bug8_step1_says_may_read_any_file():
    text = _read(BUILT_SKILL)
    step1 = _section(text, "Step 1 — Read Current State")
    assert step1 is not None, "SKILL.md must have 'Step 1 — Read Current State' section"
    lowered = step1.lower()
    # Inv 4 alignment: must mention "any file" or "freely" alongside an
    # "example"/"examples include" qualifier so the read targets aren't
    # interpreted as exhaustive.
    has_freedom = "any file" in lowered or "freely" in lowered or "may read" in lowered
    has_examples = "example" in lowered or "include" in lowered
    assert has_freedom and has_examples, \
        "Step 1 must clarify the listed reads are examples and the skill MAY read any file"


# ---------------------------------------------------------------------------
# BUG-9: SKILL.md Step 1 and spec.md must reference docs/spec/contract.md as
# a read target, not just spec.md.
# ---------------------------------------------------------------------------
def test_bug9_skill_step1_mentions_contract_md():
    text = _read(BUILT_SKILL)
    step1 = _section(text, "Step 1 — Read Current State")
    assert step1 is not None
    assert "contract.md" in step1, \
        "SKILL.md Step 1 must reference docs/spec/contract.md as a read target"


def test_bug9_spec_md_mentions_contract_md_read():
    text = _read(SPEC_MD)
    # spec.md should mention reading contract.md (in invariants or purpose)
    assert "contract.md" in text, \
        "spec.md must mention contract.md as a read target"


# ---------------------------------------------------------------------------
# BUG-10: SKILL.md "What You Do NOT Do" must NOT have a blanket "invoke any
# other skill" prohibition that contradicts Step 3 (which DOES invoke
# superpowers). Must exempt the superpowers used in Step 3.
# ---------------------------------------------------------------------------
def test_bug10_what_you_do_not_do_exempts_step3_superpowers():
    text = _read(BUILT_SKILL)
    section = _section(text, "What You Do NOT Do")
    assert section is not None
    lowered = section.lower()
    # Must not contain unqualified "invoke any other skill"
    has_blanket = re.search(r"invoke\s+any\s+other\s+skill\b", lowered) is not None
    # If blanket phrase present, it must be qualified with an exemption
    if has_blanket:
        has_exemption = (
            "except" in lowered
            or "other than" in lowered
            or "step 3" in lowered
            or "superpower" in lowered
        )
        assert has_exemption, \
            "'invoke any other skill' must be qualified to exempt Step 3 superpowers"


# ---------------------------------------------------------------------------
# BACKLOG-1: impl-suggestion schema documents optional owner / deprecation
# fields in spec.md.
# ---------------------------------------------------------------------------
def test_backlog1_spec_documents_optional_owner_and_deprecation():
    text = _read(SPEC_MD)
    # The schema or surrounding doc must mention owner and deprecation as
    # optional fields (or include them in the schema example).
    assert re.search(r"\bowner\b", text), "spec.md must mention 'owner' field for impl-suggestion"
    assert re.search(r"\bdeprecation\b", text, re.IGNORECASE), \
        "spec.md must mention 'deprecation' field for impl-suggestion"


# ---------------------------------------------------------------------------
# BACKLOG-2: build-contract.json registers rabbit-spec SKILL.md.
# ---------------------------------------------------------------------------
def test_backlog2_build_contract_registers_skill():
    with open(BUILD_CONTRACT) as f:
        data = json.load(f)
    source_path = ".claude/features/rabbit-spec/skills/rabbit-spec/SKILL.md"
    dest_path = ".claude/skills/rabbit-spec/SKILL.md"
    targets = data.get("targets", []) if isinstance(data, dict) else []
    found = False
    for t in targets:
        if isinstance(t, dict) and t.get("source") == source_path and t.get("destination") == dest_path:
            found = True
            break
    assert found, (
        f"build-contract.json must register a copy-file target from "
        f"{source_path} to {dest_path}"
    )


# ---------------------------------------------------------------------------
# BACKLOG-3: generated_at format is specified (ISO 8601 UTC). spec.md must
# describe the format.
# ---------------------------------------------------------------------------
def test_backlog3_generated_at_format_spec():
    text = _read(SPEC_MD)
    # The spec must call out an ISO format for generated_at.
    assert re.search(r"generated_at", text), "spec.md must mention generated_at"
    assert re.search(r"iso\s*8601|iso-8601|RFC\s*3339", text, re.IGNORECASE), \
        "spec.md must specify ISO 8601 (or RFC 3339) format for generated_at"


# ---------------------------------------------------------------------------
# BACKLOG-4: affected_files semantics clarified in spec and SKILL.md.
# ---------------------------------------------------------------------------
def test_backlog4_affected_files_clarified_in_spec():
    text = _read(SPEC_MD)
    # Look for explanatory prose describing affected_files semantics.
    # Must mention either "repo-relative" or "implementer will modify" or "paths the implementer".
    semantics = re.search(
        r"affected_files[^\n]{0,200}(?:repo-relative|implementer|paths\s+to\s+(?:modify|edit)|will\s+modify|will\s+touch)",
        text, re.IGNORECASE | re.DOTALL,
    )
    assert semantics is not None, \
        "spec.md must clarify affected_files semantics (e.g., repo-relative paths the implementer will modify)"


def test_backlog4_affected_files_clarified_in_skill():
    text = _read(BUILT_SKILL)
    # SKILL.md must clarify what affected_files means
    semantics = re.search(
        r"affected_files[^\n]{0,200}(?:repo-relative|implementer|modify|edit|touch|paths)",
        text, re.IGNORECASE | re.DOTALL,
    )
    assert semantics is not None, \
        "SKILL.md must clarify affected_files semantics"


# ---------------------------------------------------------------------------
# BACKLOG-5: SKILL.md documents args format ("<feature-name> <request>").
# ---------------------------------------------------------------------------
def test_backlog5_skill_documents_args_format():
    text = _read(BUILT_SKILL)
    # Already present in current SKILL.md; locked in as a regression test.
    assert re.search(r"args\s+format", text, re.IGNORECASE), \
        "SKILL.md must document 'Args format' line"
    assert re.search(r"<feature-name>\s+<request", text), \
        "SKILL.md Args format must be '<feature-name> <request...>'"


# ---------------------------------------------------------------------------
# BACKLOG-6: SKILL.md describes graceful behavior for non-existent feature-name.
# ---------------------------------------------------------------------------
def test_backlog6_skill_describes_nonexistent_feature_handling():
    text = _read(BUILT_SKILL)
    lowered = text.lower()
    # Must mention error/abort behavior when feature directory does not exist.
    has_error_path = (
        "does not exist" in lowered
        or "not found" in lowered
        or "missing feature" in lowered
        or "no such feature" in lowered
    )
    assert has_error_path, \
        "SKILL.md must describe graceful handling when feature-name does not exist"


# ---------------------------------------------------------------------------
# BACKLOG-7: feature.json carries a current 'updated' date (manual field).
# ---------------------------------------------------------------------------
def test_backlog7_feature_json_has_updated_date():
    with open(FEATURE_JSON) as f:
        data = json.load(f)
    updated = data.get("updated", "")
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", updated), \
        f"feature.json 'updated' must be ISO date YYYY-MM-DD, got {updated!r}"


# ---------------------------------------------------------------------------
# BACKLOG-8: spec.md Out of Scope MUST NOT hard-name the TDD subagent.
# ---------------------------------------------------------------------------
def test_backlog8_out_of_scope_no_tdd_subagent():
    text = _read(SPEC_MD)
    out_of_scope = _section(text, "Out of Scope")
    assert out_of_scope is not None, "spec.md must have an 'Out of Scope' section"
    lowered = out_of_scope.lower()
    assert "tdd subagent" not in lowered and "tdd-subagent" not in lowered, \
        "Out of Scope must not name 'TDD subagent' — say 'out of this skill's scope' generically"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
