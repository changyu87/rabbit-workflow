#!/usr/bin/env python3
"""Issue #685 (Housekeeping round 2, under #639): dead spec/contract weight removed.

Locks in the measured line-removal pass so the proven-dead content cannot
silently regress back onto the live doc surfaces (docs/spec.md, docs/contract.md):

  1. The `rabbit-feature-spec` skill is no longer owned by this feature — it
     was relocated to the `rabbit-spec` feature (rabbit-spec-create /
     rabbit-spec-update). No live surface may reference `rabbit-feature-spec`
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
     actually ships (the four directories under skills/).

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
    # absorbed into rabbit-spec (now rabbit-spec-create / spec-creator). Its
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
        "(now owned by rabbit-spec: rabbit-spec-create / spec-creator); remove "
        "or retarget the dead reference:\n" + "\n".join(hits)
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


def main() -> int:
    tests = [
        test_no_rabbit_feature_spec_reference,
        test_scaffold_skill_md_no_rabbit_feature_spec_reference,
        test_no_spec_seeder_reference,
        test_live_surfaces_name_only_existing_test_files,
        test_no_withdrawn_tombstone_placeholders,
        test_contract_provides_only_shipped_skills,
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
