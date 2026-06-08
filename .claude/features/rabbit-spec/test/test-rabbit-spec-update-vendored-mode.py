#!/usr/bin/env python3
"""Inv 4: rabbit-spec-update SKILL.md dual-accepts the `vendored` mode value.

Regression guard for #1043. After the #980 plugin->vendored rename,
`<repo_root>/.rabbit/.runtime/mode` now holds `vendored` (written verbatim
by `write_mode_marker`, which bridges `detect_mode`'s return value). The
SKILL.md `## Modes` section originally recognized only `standalone` and
`plugin`; following it literally, `vendored` matched neither the
`plugin` branch nor a deliberate dual-accept, so it fell through to
standalone and resolved `feature_root` to `.claude/features/<name>/`
instead of the vendored `.rabbit/rabbit-project/features/<name>/`.

This source-inspection test asserts the SKILL.md body dual-accepts
`vendored` as equivalent to `plugin` during the coexistence window:

  (a) the body mentions the `vendored` marker value at least once, and
  (b) every literal `vendored` mention sits in a context that names the
      vendored/plugin feature_root branch (`.rabbit/rabbit-project/features/`
      or the word `plugin`) — i.e. `vendored` is never described as a
      standalone-resolving value, so following the skill literally resolves
      a `vendored` marker to the vendored feature_root.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: removed when the #980 migration completes and the
    legacy `plugin` value is fully retired, leaving only `vendored`.
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


def test_inv4_vendored_value_is_mentioned() -> None:
    text = _text()
    assert "vendored" in text, (
        "SKILL.md must mention the `vendored` mode-marker value so that a "
        "`.rabbit/.runtime/mode` of `vendored` (post-#980 rename) resolves "
        "to the vendored feature_root instead of falling through to "
        "standalone (#1043)."
    )


def test_inv4_vendored_resolves_to_vendored_branch() -> None:
    """Every literal `vendored` mention must sit in a context that names
    the vendored/plugin feature_root branch — never the standalone branch.

    Check: for each line containing `vendored`, the window of four lines
    before and four lines after (inclusive) must contain
    `.rabbit/rabbit-project/features/` or `plugin` (the vendored-branch
    markers). This catches any wording that would let `vendored` resolve to
    the standalone path.
    """
    text = _text()
    lines = text.splitlines()
    needle = "vendored"
    offenders: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if needle not in line:
            continue
        lo = max(0, i - 4)
        hi = min(len(lines), i + 5)
        window = "\n".join(lines[lo:hi])
        if ".rabbit/rabbit-project/features/" in window or "plugin" in window:
            continue
        offenders.append((i + 1, line))
    assert not offenders, (
        "SKILL.md must place every `vendored` mention in a context naming "
        "the vendored/plugin feature_root branch (so `vendored` resolves to "
        "`.rabbit/rabbit-project/features/`, not standalone). Offending "
        "lines (1-indexed):\n"
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
