#!/usr/bin/env python3
"""test-install-host-gitignore-strategy-a.py — Inv 53 (#1052, Strategy A).

A vendored install lives at `<host>/.rabbit/`, and the rabbit-project features
the TDD cycle commits live UNDER `<host>/.rabbit/rabbit-project/features/<name>/`.
The previously-documented pattern gitignored the ENTIRE vendored `.rabbit/` dir
in the host repo, so every TDD-cycle git commit silently no-ops (no impl_commit,
no PR). #1060 adopted Strategy A: the installer writes the host-repo `.gitignore`
so it ignores ONLY the vendored tool tree (`.rabbit/.claude/`) and the
ephemerals (`.rabbit/.runtime/`) but NOT `.rabbit/rabbit-project/` — restoring
the cycle's git-atomicity guarantee.

This test pins, against the REAL installer helper `install.write_host_gitignore`:

  (a) a FRESH host (no `.gitignore`) → the host `.gitignore` ignores
      `.rabbit/.claude/` and `.rabbit/.runtime/`, and does NOT ignore
      `.rabbit/rabbit-project/...` (verified via `git check-ignore` semantics
      against a real git repo);
  (b) a host with a blanket `.rabbit/` ignore → the blanket line is MIGRATED
      (replaced) by the narrow A-shaped set, NOT merely appended; afterward
      `.rabbit/rabbit-project/...` is NO LONGER ignored;
  (c) re-running the helper is IDEMPOTENT — the host `.gitignore` content
      converges and does not grow on a second run;
  (d) a STANDALONE install (dst_root is NOT named `.rabbit`) leaves the host
      `.gitignore` untouched (the host-gitignore management is vendored-only).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

# Paths the host repo MUST keep tracked / MUST ignore under Strategy A.
TRACKED_PROJECT_PATH = ".rabbit/rabbit-project/features/x/docs/spec.md"
IGNORED_TOOL_PATH = ".rabbit/.claude/settings.json"
IGNORED_RUNTIME_PATH = ".rabbit/.runtime/mode"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(path: Path, *args: str):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True, text=True, env=env)


def _is_ignored(host: Path, rel: str) -> bool:
    """True iff git would ignore `rel` in the host repo (git check-ignore)."""
    # Materialize the path so check-ignore has something to evaluate.
    target = host / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n")
    res = _git(host, "check-ignore", "-q", rel)
    # exit 0 -> ignored; exit 1 -> not ignored.
    return res.returncode == 0


def test_fresh_host_a_shaped_ignore():
    """A fresh host with no .gitignore gets the A-shaped set: tool + ephemerals
    ignored, rabbit-project tracked."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        _git(host, "init", "-q")
        dst_root = host / ".rabbit"
        dst_root.mkdir()

        mod.write_host_gitignore(dst_root)

        gi = host / ".gitignore"
        assert gi.is_file(), "host .gitignore must be created"

        assert _is_ignored(host, IGNORED_TOOL_PATH), (
            ".rabbit/.claude/ must be ignored")
        assert _is_ignored(host, IGNORED_RUNTIME_PATH), (
            ".rabbit/.runtime/ must be ignored")
        assert not _is_ignored(host, TRACKED_PROJECT_PATH), (
            ".rabbit/rabbit-project/ must NOT be ignored (Strategy A); "
            f"git ignored {TRACKED_PROJECT_PATH!r}")
    print("PASS test_fresh_host_a_shaped_ignore")


def test_blanket_ignore_migrated_not_appended():
    """A host carrying a blanket `.rabbit/` ignore has it MIGRATED (replaced) to
    the narrow A-shaped set — the over-broad line is gone, not merely shadowed,
    and rabbit-project is no longer ignored."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        _git(host, "init", "-q")
        # Pre-existing host gitignore with the blanket vendored ignore plus an
        # unrelated user entry that MUST be preserved.
        (host / ".gitignore").write_text(
            "node_modules/\n"
            ".rabbit/\n"
            "*.log\n"
        )
        dst_root = host / ".rabbit"
        dst_root.mkdir()

        mod.write_host_gitignore(dst_root)

        content = (host / ".gitignore").read_text()
        # The blanket line is replaced — no standalone `.rabbit/` line remains.
        lines = [ln.strip() for ln in content.splitlines()]
        assert ".rabbit/" not in lines, (
            "blanket `.rabbit/` ignore must be MIGRATED away, not retained; "
            f"got lines {lines}")
        # Unrelated user entries are preserved.
        assert "node_modules/" in lines, "unrelated entry must be preserved"
        assert "*.log" in lines, "unrelated entry must be preserved"

        # And the behavioural consequence: rabbit-project is tracked again.
        assert _is_ignored(host, IGNORED_TOOL_PATH), (
            ".rabbit/.claude/ must remain ignored after migration")
        assert _is_ignored(host, IGNORED_RUNTIME_PATH), (
            ".rabbit/.runtime/ must remain ignored after migration")
        assert not _is_ignored(host, TRACKED_PROJECT_PATH), (
            "after migration .rabbit/rabbit-project/ must NOT be ignored")
    print("PASS test_blanket_ignore_migrated_not_appended")


def test_idempotent_on_rerun():
    """Re-running the helper converges: the host .gitignore content is stable
    and does not grow on a second invocation."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        _git(host, "init", "-q")
        (host / ".gitignore").write_text(".rabbit/\n")
        dst_root = host / ".rabbit"
        dst_root.mkdir()

        mod.write_host_gitignore(dst_root)
        first = (host / ".gitignore").read_text()
        mod.write_host_gitignore(dst_root)
        second = (host / ".gitignore").read_text()

        assert first == second, (
            "host .gitignore must be idempotent on re-run; "
            f"first={first!r} second={second!r}")
        # No duplicate ignore tokens.
        for token in (".rabbit/.claude/", ".rabbit/.runtime/"):
            assert second.count(token) == 1, (
                f"token {token!r} must appear exactly once; got {second!r}")
    print("PASS test_idempotent_on_rerun")


def test_standalone_install_untouched():
    """A standalone install (dst_root not named `.rabbit`) leaves the host
    .gitignore untouched — host-gitignore management is vendored-only."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        _git(host, "init", "-q")
        before = "my-existing-ignores/\n"
        (host / ".gitignore").write_text(before)
        # Standalone: the install root IS the repo (not a `.rabbit` subdir).
        dst_root = host
        mod.write_host_gitignore(dst_root)
        after = (host / ".gitignore").read_text()
        assert after == before, (
            "standalone install must NOT touch the host .gitignore; "
            f"before={before!r} after={after!r}")
    print("PASS test_standalone_install_untouched")


def main() -> int:
    test_fresh_host_a_shaped_ignore()
    test_blanket_ignore_migrated_not_appended()
    test_idempotent_on_rerun()
    test_standalone_install_untouched()
    return 0


if __name__ == "__main__":
    sys.exit(main())
