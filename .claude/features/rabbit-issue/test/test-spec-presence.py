#!/usr/bin/env python3
"""Presence and frontmatter tests for rabbit-issue spec.md and contract.md.

Spec-side invariants enforced (per spec-rules.md §3):

  1. spec.md MUST exist with a YAML frontmatter block carrying
     feature / version / owner / deprecation_criterion.
  2. contract.md MUST exist with the same frontmatter shape.
  3. The canonical layout is `specs/` (issue #399 Phase 2). The legacy
     `docs/spec/` directory MUST be gone for rabbit-issue.

Spec paths resolve dual-read (specs/ preferred, docs/spec/ fallback) so
the presence checks survive the migration window; invariant #3 separately
pins that rabbit-issue has completed the cutover.

These are static checks; they do not exercise runtime behaviour.

Version: 1.1.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
from __future__ import annotations

import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]

REQUIRED_FM_KEYS = ("feature:", "version:", "owner:", "deprecation_criterion:")


def resolve_spec_path(feature_dir: Path, name: str) -> Path:
    """Prefer <feature_dir>/specs/<name>; fall back to docs/spec/<name>.

    Mirrors the contract feature's dual-read resolver so the presence
    checks survive the docs/spec/ -> specs/ migration window.
    """
    preferred = feature_dir / "specs" / name
    if preferred.is_file():
        return preferred
    return feature_dir / "docs" / "spec" / name


SPEC_MD = resolve_spec_path(FEATURE_DIR, "spec.md")
CONTRACT_MD = resolve_spec_path(FEATURE_DIR, "contract.md")


def check(path: Path) -> list[str]:
    """Return a list of failure messages for `path` (empty list = pass)."""
    fails = []
    if not path.is_file():
        fails.append(f"{path} does not exist")
        return fails
    text = path.read_text()
    if not text.startswith("---\n"):
        fails.append(f"{path} missing leading YAML frontmatter block")
        return fails
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        fails.append(f"{path} has unterminated YAML frontmatter")
        return fails
    fm = parts[1]
    for key in REQUIRED_FM_KEYS:
        if key not in fm:
            fails.append(f"{path} frontmatter missing key '{key}'")
    return fails


def check_specs_cutover() -> list[str]:
    """Invariant #3: specs/ is canonical and docs/spec/ is gone."""
    fails = []
    specs_spec = FEATURE_DIR / "specs" / "spec.md"
    if not specs_spec.is_file():
        fails.append(f"{specs_spec} does not exist (specs/ is the canonical layout)")
    legacy = FEATURE_DIR / "docs" / "spec"
    if legacy.exists():
        fails.append(f"{legacy} still present; docs/spec/ must be removed after migration")
    return fails


def main() -> int:
    all_fails: list[str] = []
    for p in (SPEC_MD, CONTRACT_MD):
        all_fails.extend(check(p))
    all_fails.extend(check_specs_cutover())
    if all_fails:
        for msg in all_fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-spec-presence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
