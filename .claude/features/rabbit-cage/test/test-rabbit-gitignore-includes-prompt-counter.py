#!/usr/bin/env python3
"""test-rabbit-gitignore-includes-prompt-counter.py — #1135.

`install.write_rabbit_gitignore(dst_root)` writes the vendored inner
`.rabbit/.gitignore` whose job is to keep rabbit-owned per-session ephemerals
out of version control. `.rabbit-prompt-counter` is exactly such a
per-session ephemeral — the dispatcher hooks rewrite it every session (it is
listed in `feature.json` runtime config and is stripped from the workspace
tree by `scripts/workspace-tree.py`) — yet the ephemeral list omitted it
alongside its sibling `.rabbit-restart-snapshot`.

Under Strategy D full-vendor (#1086) the host repo tracks the whole `.rabbit/`
tree, so an un-ignored `.rabbit-prompt-counter` gets committed and then churns
the working tree every session (observed blocking `git checkout main` after a
PR merge on v10.34.1).

This test pins, against the REAL installer helper, that the generated inner
`.gitignore` content lists `.rabbit-prompt-counter` (alongside the existing
`.rabbit-restart-snapshot` ephemeral).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rabbit_gitignore_lists_prompt_counter():
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        dst_root = Path(td).resolve()
        mod.write_rabbit_gitignore(dst_root)

        gi = dst_root / ".gitignore"
        assert gi.is_file(), "inner .rabbit/.gitignore must be created"
        lines = [ln.strip() for ln in gi.read_text().splitlines()]

        # Sanity: the existing per-session ephemeral is still listed.
        assert ".rabbit-restart-snapshot" in lines, (
            ".rabbit-restart-snapshot must remain in the ephemeral ignore list; "
            f"got {lines}")
        # The fix: the prompt counter is also ignored.
        assert ".rabbit-prompt-counter" in lines, (
            ".rabbit-prompt-counter (per-session ephemeral rewritten by the "
            "dispatcher hooks) MUST be in the ephemeral ignore list so it is "
            "never committed (#1135); "
            f"got {lines}")
    print("PASS test_rabbit_gitignore_lists_prompt_counter")


def main() -> int:
    test_rabbit_gitignore_lists_prompt_counter()
    return 0


if __name__ == "__main__":
    sys.exit(main())
