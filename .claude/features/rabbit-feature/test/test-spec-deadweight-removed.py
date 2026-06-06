#!/usr/bin/env python3
"""Issue #685 (Housekeeping round 2, under #639): dead spec/contract weight removed.

Locks in the measured line-removal pass so the proven-dead content cannot
silently regress back onto the live doc surfaces (docs/spec.md, docs/contract.md):

  1. The `rabbit-feature-spec` skill is no longer owned by this feature — it
     was relocated to the `rabbit-spec` feature (the rabbit-spec-creator
     subagent / rabbit-spec-update). No live surface may reference `rabbit-feature-spec`
     or its retired invariant section. Verified dead: the skill directory
     `skills/rabbit-feature-spec/` does not exist. (Issue #700 extends this to
     the `rabbit-feature-scaffold` SKILL.md "What You Do NOT Do" example.)

  2. The live surfaces (spec.md Tests section and contract.md lock strings)
     may only name test files that actually exist under test/. Stale mappings
     to deleted/renamed test files (test-build-source.py, test-spec-skill.py,
     test-prompts-declared.py, test-scope-script-resolve-scope.py) are dead
     and must not be listed.

  3. No `*(Withdrawn — folded into CHANGELOG.md.)*` tombstone placeholders
     remain in spec.md. The retired-invariant prose lives in CHANGELOG.md;
     the per-number gap is preserved implicitly by the surviving numbering,
     not by a placeholder line. No test asserts these placeholders exist.

  4. The contract.md provides.skills block lists only skills this feature
     actually ships (the directories under skills/).

  5. The `rabbit-feature-audit` skill is retired (issue #853): its
     deprecation criterion ("validate_feature exposed via a first-class CLI
     in the contract feature") is met by contract's validate-feature.py
     (single-feature + `all` sweep). Auditing is run directly via that
     script (script-tier). No live surface (spec.md, contract.md,
     feature.json manifest/surface) may reference the retired skill, and the
     skill directory must be gone. The standalone team-owner check
     `scripts/audit-owner.py` survives and is run directly.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when a cross-feature dead-content / surface-vs-disk
validator subsumes this per-feature guard.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs/spec.md"
CONTRACT_MD = FEATURE_DIR / "docs/contract.md"
SKILLS_DIR = FEATURE_DIR / "skills"
TEST_DIR = FEATURE_DIR / "test"
SCAFFOLD_SKILL_MD = SKILLS_DIR / "rabbit-feature-scaffold/SKILL.md"

LIVE_SURFACES = [SPEC_MD, CONTRACT_MD]


def _contract_block() -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", CONTRACT_MD.read_text(), re.DOTALL)
    assert m, "contract.md missing JSON block"
    return json.loads(m.group(1))


def test_no_rabbit_feature_spec_reference() -> None:
    # Prove-it-dead precondition: the skill directory is gone.
    assert not (SKILLS_DIR / "rabbit-feature-spec").exists(), (
        "rabbit-feature-spec skill dir still exists; this guard assumes it was "
        "relocated to the rabbit-spec feature"
    )
    hits: list[str] = []
    for surface in LIVE_SURFACES:
        for i, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), 1):
            if "rabbit-feature-spec" in line:
                hits.append(f"{surface.relative_to(FEATURE_DIR)}:{i}: {line.strip()}")
    assert not hits, (
        "live surfaces reference the relocated rabbit-feature-spec skill "
        "(now owned by rabbit-spec); remove the dead reference:\n"
        + "\n".join(hits)
    )


def test_scaffold_skill_md_no_rabbit_feature_spec_reference() -> None:
    # Issue #700: the rabbit-feature-scaffold SKILL.md "What You Do NOT Do"
    # section named the relocated rabbit-feature-spec skill as a do-not-invoke
    # example. The skill no longer exists under this feature; the live SKILL.md
    # must not name it.
    assert not (SKILLS_DIR / "rabbit-feature-spec").exists(), (
        "rabbit-feature-spec skill dir still exists; this guard assumes it was "
        "relocated to the rabbit-spec feature"
    )
    assert SCAFFOLD_SKILL_MD.exists(), f"missing SKILL.md: {SCAFFOLD_SKILL_MD}"
    hits = [
        f"{SCAFFOLD_SKILL_MD.relative_to(FEATURE_DIR)}:{i}: {line.strip()}"
        for i, line in enumerate(
            SCAFFOLD_SKILL_MD.read_text(encoding="utf-8").splitlines(), 1
        )
        if "rabbit-feature-spec" in line
    ]
    assert not hits, (
        "rabbit-feature-scaffold SKILL.md references the relocated "
        "rabbit-feature-spec skill (now owned by rabbit-spec); replace the dead "
        "example with the live successor or remove it:\n" + "\n".join(hits)
    )


def test_live_surfaces_name_only_existing_test_files() -> None:
    existing = {p.name for p in TEST_DIR.glob("test-*.py")}
    ghosts: dict[str, list[str]] = {}
    for surface in LIVE_SURFACES:
        named = set(
            re.findall(r"\b(test-[\w\-]+\.py)\b", surface.read_text(encoding="utf-8"))
        )
        missing = sorted(named - existing)
        if missing:
            ghosts[str(surface.relative_to(FEATURE_DIR))] = missing
    assert not ghosts, (
        "live surfaces name test files that do not exist under test/ "
        f"(stale spec/contract references): {ghosts}"
    )


def test_no_spec_seeder_reference() -> None:
    # Issue #717 (housekeeping under #639): the `spec-seeder` feature was
    # absorbed into rabbit-spec (now the rabbit-spec-creator subagent). Its
    # feature directory and dispatch script are gone; live surfaces must not
    # name the dead feature dir or its retired dispatcher.
    assert not (
        FEATURE_DIR.parent / "spec-seeder"
    ).exists(), (
        "spec-seeder feature dir still exists; this guard assumes it was "
        "absorbed into the rabbit-spec feature"
    )
    dead_tokens = (
        "spec-seeder",
        "dispatch-spec-seeder.py",
        ".claude/features/spec-seeder",
    )
    hits: list[str] = []
    for surface in LIVE_SURFACES:
        for i, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), 1):
            if any(tok in line for tok in dead_tokens):
                hits.append(f"{surface.relative_to(FEATURE_DIR)}:{i}: {line.strip()}")
    assert not hits, (
        "live surfaces reference the absorbed spec-seeder feature "
        "(now owned by rabbit-spec: the rabbit-spec-creator subagent); remove "
        "or retarget the dead reference:\n" + "\n".join(hits)
    )


SCAFFOLD_SCRIPT = FEATURE_DIR / "scripts/scaffold-feature.py"


def test_no_retired_spec_create_reference() -> None:
    # Issue #922: the rabbit-spec-create SKILL is retired. The
    # rabbit-spec-creator subagent now writes its own docs/spec.md and is
    # dispatched DIRECTLY; rabbit-spec's renamed input assembler is
    # dispatch-spec-creator.py. No rabbit-feature surface may name the retired
    # skill or the old dispatch-spec-create.py script name; the plugin-mode
    # handoff surfaces (SKILL.md, scaffold-feature.py, spec.md, contract.md)
    # must name dispatch-spec-creator.py + the rabbit-spec-creator subagent.
    dead_tokens = ("dispatch-spec-create.py",)
    surfaces = [SPEC_MD, CONTRACT_MD, SCAFFOLD_SKILL_MD, SCAFFOLD_SCRIPT]
    hits: list[str] = []
    for surface in surfaces:
        for i, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), 1):
            if any(tok in line for tok in dead_tokens):
                hits.append(f"{surface.relative_to(FEATURE_DIR)}:{i}: {line.strip()}")
            # "rabbit-spec-create" but not "rabbit-spec-creator"
            stripped = line.replace("rabbit-spec-creator", "")
            if "rabbit-spec-create" in stripped:
                hits.append(f"{surface.relative_to(FEATURE_DIR)}:{i}: {line.strip()}")
    assert not hits, (
        "rabbit-feature surfaces reference the retired rabbit-spec-create skill "
        "or the old dispatch-spec-create.py script name (#922); retarget to "
        "dispatch-spec-creator.py + direct rabbit-spec-creator dispatch:\n"
        + "\n".join(hits)
    )
    # Positive: the live plugin-mode handoff surfaces name the new path.
    for surface in (SCAFFOLD_SKILL_MD, SCAFFOLD_SCRIPT):
        text = surface.read_text(encoding="utf-8")
        assert "dispatch-spec-creator.py" in text, (
            f"{surface.relative_to(FEATURE_DIR)} must name dispatch-spec-creator.py"
        )
        assert "rabbit-spec-creator" in text, (
            f"{surface.relative_to(FEATURE_DIR)} must name the rabbit-spec-creator subagent"
        )


def test_no_withdrawn_tombstone_placeholders() -> None:
    hits = [
        f"docs/spec.md:{i}: {line.strip()}"
        for i, line in enumerate(SPEC_MD.read_text(encoding="utf-8").splitlines(), 1)
        if "Withdrawn — folded into CHANGELOG" in line
    ]
    assert not hits, (
        "spec.md still carries Withdrawn tombstone placeholders; the retired "
        "prose lives in CHANGELOG.md, so the placeholder lines are dead weight:\n"
        + "\n".join(hits)
    )


TOUCH_SKILL_MD = SKILLS_DIR / "rabbit-feature-touch/SKILL.md"

# Restated rationale / history that a measured reduction wave cut from the live
# doc surfaces. Each fragment's load-bearing content survives elsewhere (the
# behavioural spec line, a test docstring, or CHANGELOG.md); the restated copy
# on the live surface is dead weight that must not regrow.
DEAD_RESTATEMENT_FRAGMENTS = [
    # spec.md Inv 44 — history of the pre-walk-up single-check semantics. The
    # walk-up behaviour itself remains specified; the "replaces the original"
    # backstory lives in the test docstring + CHANGELOG.
    "replaces the original single-check semantics",
    # spec.md Inv 56 — restated rationale for the removed specs/ fallback. The
    # behavioural spec (prefer flat docs/, fall back to legacy docs/spec/)
    # remains; the "dead specs/ fallback is removed" backstory is history.
    "fallback is removed",
]


def test_live_surfaces_no_restated_rationale() -> None:
    surfaces = [SPEC_MD, CONTRACT_MD, TOUCH_SKILL_MD]
    hits: list[str] = []
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        for frag in DEAD_RESTATEMENT_FRAGMENTS:
            if frag in text:
                hits.append(f"{surface.relative_to(FEATURE_DIR)}: {frag!r}")
    assert not hits, (
        "live surfaces carry restated rationale/history cut by the reduction "
        "wave; the load-bearing content survives in the behavioural spec line "
        "or CHANGELOG, so the restated copy is dead weight:\n" + "\n".join(hits)
    )


def test_contract_provides_only_shipped_skills() -> None:
    shipped = {
        f".claude/features/rabbit-feature/skills/{d.name}/"
        for d in SKILLS_DIR.iterdir()
        if d.is_dir()
    }
    provided = {s["path"] for s in _contract_block()["provides"]["skills"]}
    extra = sorted(provided - shipped)
    assert not extra, (
        "contract.md provides.skills lists skills not shipped under skills/: "
        f"{extra}"
    )


FEATURE_JSON = FEATURE_DIR / "feature.json"
AUDIT_SKILL_DIR = SKILLS_DIR / "rabbit-feature-audit"
AUDIT_OWNER_SCRIPT = FEATURE_DIR / "scripts/audit-owner.py"


def test_audit_skill_retired() -> None:
    # Issue #853: the rabbit-feature-audit skill is retired now that contract's
    # validate-feature.py exposes single-feature + `all` sweep validation. The
    # skill directory must be gone and no live surface may reference it.
    assert not AUDIT_SKILL_DIR.exists(), (
        "skills/rabbit-feature-audit/ still exists; the audit skill is retired "
        "(auditing runs directly via contract's validate-feature.py)"
    )
    data = json.loads(FEATURE_JSON.read_text())
    surface_skills = data.get("surface", {}).get("skills", [])
    assert "skills/rabbit-feature-audit/SKILL.md" not in surface_skills, (
        "feature.json surface.skills still lists the retired rabbit-feature-audit skill"
    )
    manifest_sources = [
        e.get("args", {}).get("source")
        for e in data.get("manifest", [])
        if e.get("api") == "publish_skill"
    ]
    assert "skills/rabbit-feature-audit/SKILL.md" not in manifest_sources, (
        "feature.json manifest still publishes the retired rabbit-feature-audit skill"
    )
    provided = {s["path"] for s in _contract_block()["provides"]["skills"]}
    audit_path = ".claude/features/rabbit-feature/skills/rabbit-feature-audit/"
    assert audit_path not in provided, (
        "contract.md provides.skills still lists the retired rabbit-feature-audit skill"
    )
    hits: list[str] = []
    for surface in LIVE_SURFACES:
        for i, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), 1):
            if "rabbit-feature-audit" in line:
                hits.append(f"{surface.relative_to(FEATURE_DIR)}:{i}: {line.strip()}")
    assert not hits, (
        "live surfaces reference the retired rabbit-feature-audit skill; auditing "
        "is now run directly via contract's validate-feature.py:\n" + "\n".join(hits)
    )


def test_audit_owner_script_survives() -> None:
    # The standalone team-owner enforcement script is NOT retired — it enforces
    # a rule (Inv 50) that validate_feature does not cover. It survives and is
    # run directly (script-tier).
    import os
    assert AUDIT_OWNER_SCRIPT.is_file(), (
        "scripts/audit-owner.py must survive the audit-skill retirement"
    )
    assert os.access(AUDIT_OWNER_SCRIPT, os.X_OK), (
        "scripts/audit-owner.py must remain executable"
    )


def main() -> int:
    tests = [
        test_no_rabbit_feature_spec_reference,
        test_scaffold_skill_md_no_rabbit_feature_spec_reference,
        test_no_spec_seeder_reference,
        test_no_retired_spec_create_reference,
        test_live_surfaces_name_only_existing_test_files,
        test_no_withdrawn_tombstone_placeholders,
        test_live_surfaces_no_restated_rationale,
        test_contract_provides_only_shipped_skills,
        test_audit_skill_retired,
        test_audit_owner_script_survives,
    ]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
