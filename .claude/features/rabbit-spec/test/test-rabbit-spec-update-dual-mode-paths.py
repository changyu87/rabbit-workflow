#!/usr/bin/env python3
"""Inv 5: rabbit-spec-update SKILL.md dual-mode feature_root resolution.

Source-inspection-only test. Asserts the SKILL.md body documents mode
detection from `.rabbit/.runtime/mode`, the plugin-mode prefix
`.rabbit/rabbit-project/features/`, and that every literal occurrence
of `.claude/features/` (the standalone-only path) appears in a context
that names the standalone branch — i.e. no unconditional uses of the
standalone-only path.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-spec-update is absorbed into a
native rabbit CLI command that owns its own mode resolution.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_MD = (
    Path(__file__).resolve().parents[1]
    / "skills/rabbit-spec-update/SKILL.md"
)


def _text() -> str:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    return SKILL_MD.read_text()


def test_inv5_mode_marker_is_mentioned() -> None:
    text = _text()
    assert ".rabbit/.runtime/mode" in text, (
        "SKILL.md must mention the mode marker path "
        "'.rabbit/.runtime/mode' (mode detection contract)"
    )


def test_inv5_plugin_feature_root_is_mentioned() -> None:
    text = _text()
    assert ".rabbit/rabbit-project/features/" in text, (
        "SKILL.md must mention the plugin-mode feature root prefix "
        "'.rabbit/rabbit-project/features/'"
    )


def test_inv5_standalone_paths_are_qualified() -> None:
    """Every literal occurrence of '.claude/features/' must appear in
    a context that names the standalone-mode branch.

    Check: for each line containing '.claude/features/', the window of
    four lines before and four lines after (inclusive) must contain
    'standalone' or 'Standalone'. This catches unconditional uses of
    the standalone-only path.
    """
    text = _text()
    lines = text.splitlines()
    needle = ".claude/features/"
    offenders: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if needle not in line:
            continue
        lo = max(0, i - 4)
        hi = min(len(lines), i + 5)
        window = "\n".join(lines[lo:hi])
        if "standalone" in window or "Standalone" in window:
            continue
        offenders.append((i + 1, line))
    assert not offenders, (
        "SKILL.md must qualify every occurrence of '.claude/features/' "
        "with standalone-mode context (no unconditional uses of the "
        "standalone-only path). Offending lines (1-indexed):\n"
        + "\n".join(f"  L{n}: {ln}" for n, ln in offenders)
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
