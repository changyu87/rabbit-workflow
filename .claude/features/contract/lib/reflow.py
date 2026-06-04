"""contract.lib.reflow — deterministic invariant-renumber (reflow) tool.

Closes numbering gaps in a feature's `spec.md` Invariants sections so the
surviving invariants are numbered contiguously 1..N, and atomically rewrites
every cross-reference to a renumbered (live) invariant across the feature's
own surfaces (spec.md, contract.md, skills/*/SKILL.md, lib/*.py,
scripts/**/*.py, test/*.py, templates/**).

Why a script (not a prompt): mandating contiguous numbering (contract Inv 30)
means removing an invariant forces renumbering every higher invariant AND
rewriting every `Inv N` cross-reference. Doing that by hand or by prompt WILL
break references. This module owns the renumber+rewrite as a single
deterministic, all-or-nothing pass.

Design guarantees:

  * Live-only mapping. The renumber map is built ONLY from invariant numbers
    that currently appear as top-level items in the feature's spec Invariants
    sections (the "live" set). Numbers absent from the body (gaps left by
    retired invariants) are NEVER source keys, so a reference to a retired
    invariant number (e.g. a CHANGELOG tombstone's `Inv 55`) is left
    untouched — it points at history, not at a live invariant.

  * Single atomic pass. Every `Inv <n>` reference is rewritten in ONE pass via
    a regex callback that looks up `map[n]`; references whose number is not in
    the map are left verbatim. This avoids the cascade bug of sequential
    `Inv 5 -> Inv 4; Inv 4 -> Inv 4` replacements (which would double-map).

  * CHANGELOG excluded by default. `docs/CHANGELOG.md` records point-in-time
    tombstones ("Inv 30 carried a parenthetical") whose numbers are correct
    AS OF the retirement; rewriting them would corrupt history. The reflow
    therefore never touches the CHANGELOG.

  * Leading-number rewrite is section-scoped. Only top-level `N. ` invariant
    list items inside an Invariants section (outside fenced code) have their
    leading number rewritten; ordinary numbered lists elsewhere are left
    alone, exactly mirroring `check_invariant_monotonic_order`'s parser.

Contract / interface:

    reflow_feature(feature_dir, *, dry_run=False) -> ReflowResult

  Returns a ReflowResult describing the old->new map, the files changed, and
  (in dry_run) the would-be edits without writing. With dry_run=False it
  writes every changed file in place and returns the same report.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when invariant numbering is folded into a
structured, schema-tracked log that renumbers via data rather than text.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List

from lib.checks import resolve_spec_path

_INVARIANTS_HEADING_RE = re.compile(r"^(##|###)\s+Invariants\b")
_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+")
_NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.\s")

# Cross-reference token: "Inv 30", "Inv 30a". The optional trailing letter
# (sub-invariant suffix, e.g. Inv 28b) is preserved verbatim — only the
# integer is remapped, and a suffixed reference is remapped iff its base
# integer is live.
_INV_REF_RE = re.compile(r"\bInv (\d+)([a-z]?)\b")

# File suffixes whose `Inv N` references are rewritten when scanning a feature.
_REWRITE_SUFFIXES = (".py", ".md", ".txt", ".json")


@dataclass
class ReflowResult:
    """Outcome of a reflow pass.

    feature      - feature name (basename of feature_dir).
    renumber_map - {old_number: new_number} for every LIVE invariant whose
                   number changed (identity entries are omitted).
    files_changed- absolute paths of files that changed.
    edits        - {path: (old_text, new_text)} for dry-run inspection.
    messages     - human-readable summary lines.
    ok           - True iff the pass completed (False if spec missing /
                   unparsable).
    """

    feature: str
    renumber_map: Dict[int, int] = field(default_factory=dict)
    files_changed: List[str] = field(default_factory=list)
    edits: Dict[str, tuple] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)
    ok: bool = True


def extract_live_numbers(spec_text: str) -> List[int]:
    """Return the ordered list of top-level invariant numbers that appear in
    the spec's Invariants sections (outside fenced code), in document order.

    Mirrors check_invariant_monotonic_order's parser so the live set the
    reflow renumbers is exactly the set the check validates.
    """
    nums: List[int] = []
    in_section = False
    in_fence = False
    for line in spec_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _ANY_HEADING_RE.match(line):
            in_section = bool(_INVARIANTS_HEADING_RE.match(line))
            continue
        if not in_section:
            continue
        m = _NUMBERED_ITEM_RE.match(line)
        if m:
            nums.append(int(m.group(1)))
    return nums


def build_renumber_map(live_numbers: List[int]) -> Dict[int, int]:
    """Map each live number to its contiguous 1..N position, keeping document
    order. Identity entries (already in the right slot) are omitted.
    """
    out: Dict[int, int] = {}
    for idx, old in enumerate(live_numbers, start=1):
        if old != idx:
            out[old] = idx
    return out


def _rewrite_refs(text: str, renumber_map: Dict[int, int]) -> str:
    """Rewrite every `Inv <n>` whose base integer is a live, renumbered key."""

    def repl(m: "re.Match") -> str:
        n = int(m.group(1))
        suffix = m.group(2)
        if n in renumber_map:
            return f"Inv {renumber_map[n]}{suffix}"
        return m.group(0)

    return _INV_REF_RE.sub(repl, text)


def _rewrite_leading_numbers(spec_text: str, renumber_map: Dict[int, int]) -> str:
    """Rewrite the leading `N. ` of each top-level Invariants-section item to
    its mapped number. Section/fence tracking mirrors the parser above.
    """
    out_lines: List[str] = []
    in_section = False
    in_fence = False
    for line in spec_text.splitlines(keepends=True):
        body = line.rstrip("\n").rstrip("\r")
        stripped = body.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        if _ANY_HEADING_RE.match(body):
            in_section = bool(_INVARIANTS_HEADING_RE.match(body))
            out_lines.append(line)
            continue
        if in_section:
            m = _NUMBERED_ITEM_RE.match(body)
            if m:
                old = int(m.group(1))
                if old in renumber_map:
                    new = renumber_map[old]
                    line = re.sub(rf"^{old}\.", f"{new}.", line, count=1)
        out_lines.append(line)
    return "".join(out_lines)


def _feature_surface_files(feature_dir: str) -> List[str]:
    """Collect the per-feature surfaces whose `Inv N` references the reflow
    rewrites, EXCLUDING CHANGELOG.md (immutable history), any docs/bugs/
    subtree, and VCS/cache dirs.
    """
    files: List[str] = []
    for root, dirs, names in os.walk(feature_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "bugs")]
        for name in sorted(names):
            if not name.endswith(_REWRITE_SUFFIXES):
                continue
            if name == "CHANGELOG.md":
                continue
            files.append(os.path.join(root, name))
    return sorted(files)


def reflow_feature(feature_dir: str, *, dry_run: bool = False) -> ReflowResult:
    """Renumber a feature's invariants to contiguous 1..N and rewrite all
    live cross-references across the feature's own surfaces.

    feature_dir - the feature root (contains feature.json, docs/, etc.).
    dry_run     - when True, compute the map + edits but write nothing.
    """
    feat_name = os.path.basename(os.path.realpath(feature_dir))
    result = ReflowResult(feature=feat_name)

    spec_path = resolve_spec_path(feature_dir, "spec.md")
    if not os.path.isfile(spec_path):
        result.ok = False
        result.messages.append(f"ERROR: no spec.md for {feat_name} at {spec_path}")
        return result

    try:
        spec_text = _read(spec_path)
    except OSError as e:
        result.ok = False
        result.messages.append(f"ERROR: cannot read {spec_path}: {e}")
        return result

    live = extract_live_numbers(spec_text)
    if not live:
        result.messages.append(
            f"OK: {feat_name} has no numbered invariants — nothing to reflow"
        )
        return result

    renumber_map = build_renumber_map(live)
    result.renumber_map = dict(renumber_map)

    if not renumber_map:
        result.messages.append(
            f"OK: {feat_name} already contiguous (1..{len(live)}) — no reflow needed"
        )
        return result

    result.messages.append(
        f"reflow {feat_name}: {len(renumber_map)} invariant(s) renumbered "
        f"(now contiguous 1..{len(live)})"
    )

    # 1. Rewrite spec.md leading item numbers FIRST, then its Inv-references.
    new_spec = _rewrite_leading_numbers(spec_text, renumber_map)
    new_spec = _rewrite_refs(new_spec, renumber_map)
    _stage(result, spec_path, spec_text, new_spec)

    # 2. Rewrite Inv-references across every other surface.
    for path in _feature_surface_files(feature_dir):
        if os.path.realpath(path) == os.path.realpath(spec_path):
            continue
        try:
            text = _read(path)
        except (OSError, UnicodeDecodeError):
            continue
        new_text = _rewrite_refs(text, renumber_map)
        _stage(result, path, text, new_text)

    if not dry_run:
        for path in result.files_changed:
            _write(path, result.edits[path][1])

    result.messages.append(
        f"{'would change' if dry_run else 'changed'} {len(result.files_changed)} file(s)"
    )
    return result


def _stage(result: ReflowResult, path: str, old: str, new: str) -> None:
    if old != new:
        result.files_changed.append(path)
        result.edits[path] = (old, new)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
