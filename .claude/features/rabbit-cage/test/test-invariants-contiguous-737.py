#!/usr/bin/env python3
"""test-invariants-contiguous-737.py — #737.

End-to-end guard for the reflow + opt-in feature touch:

  (a) the spec.md `## Invariants` section numbers its top-level items
      contiguously 1..N with no holes (the gaps at old 24 and 26 are closed);
  (b) the feature's invariant numbering is internally consistent — re-running
      the deterministic reflow tool (`contract/scripts/reflow-invariants.py`)
      in --dry-run reports ZERO renumbering and ZERO files-to-change. That is
      the authoritative "no dangling cage-local `Inv N` reference" check: the
      reflow tool owns the exact definition of a cage-local invariant
      reference (every `Inv N` whose base integer is one of THIS feature's
      live invariant numbers); if any such reference were inconsistent with
      the contiguous numbering, a fresh reflow would rewrite it and the
      dry-run would report a change. Cross-feature delegations (`contract
      Inv 66`, `rabbit-auto-evolve Inv 31`) cite OTHER features' numbering and
      are deliberately out of the tool's scope, so they never trip this check;
  (c) feature.json opts into the strict tier via
      `"contiguous_invariants": true`.

docs/CHANGELOG.md is never reflowed (its tombstones are point-in-time history
that intentionally cite pre-reflow numbers), so it is outside both checks.
"""

import json
import re
import sys
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]
REPO_ROOT = CAGE.parents[2]  # <repo>/.claude/features/rabbit-cage -> <repo>
REFLOW_LIB = (
    REPO_ROOT / ".claude" / "features" / "contract" / "lib" / "reflow.py")

_INV_HEADING_RE = re.compile(r"^(##|###)\s+Invariants\b")
_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+")
_NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.\s")


def _resolve_spec() -> Path:
    docs = CAGE / "docs" / "spec.md"
    return docs if docs.is_file() else CAGE / "specs" / "spec.md"


def _invariant_numbers(spec_path: Path):
    nums = []
    in_section = False
    in_fence = False
    for line in spec_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _ANY_HEADING_RE.match(line):
            in_section = bool(_INV_HEADING_RE.match(line))
            continue
        if not in_section:
            continue
        m = _NUMBERED_ITEM_RE.match(line)
        if m:
            nums.append(int(m.group(1)))
    return nums


def _load_reflow():
    # reflow.py does `from lib.checks import ...`, so the contract feature dir
    # must be importable as the package root.
    contract_dir = str(REFLOW_LIB.parents[1])  # .../features/contract
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    from lib.reflow import reflow_feature  # noqa: E402
    return reflow_feature


def main() -> int:
    spec_path = _resolve_spec()
    assert spec_path.is_file(), f"spec.md not found at {spec_path}"

    # (a) contiguous 1..N
    nums = _invariant_numbers(spec_path)
    assert nums, "no numbered invariants found in spec.md Invariants section"
    expected = list(range(1, len(nums) + 1))
    assert nums == expected, (
        f"invariants not contiguous 1..{len(nums)}: got {nums}")
    n = len(nums)
    print(f"PASS contiguous: invariants 1..{n} (no holes)")

    # (b) reflow is a no-op (no dangling cage-local Inv refs)
    assert REFLOW_LIB.is_file(), f"reflow lib not found at {REFLOW_LIB}"
    reflow_feature = _load_reflow()
    result = reflow_feature(str(CAGE), dry_run=True)
    assert result.ok, f"reflow dry-run failed: {result.messages}"
    assert not result.renumber_map, (
        "spec is NOT already contiguous — reflow dry-run would renumber: "
        f"{result.renumber_map}")
    assert not result.files_changed, (
        "dangling cage-local Inv references remain — reflow dry-run would "
        f"rewrite: {result.files_changed}")
    print("PASS reflow dry-run is a no-op (numbering internally consistent)")

    # (c) opt-in flag set
    fj = json.loads((CAGE / "feature.json").read_text())
    assert fj.get("contiguous_invariants") is True, (
        "feature.json must set \"contiguous_invariants\": true")
    print("PASS contiguous_invariants opt-in set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
