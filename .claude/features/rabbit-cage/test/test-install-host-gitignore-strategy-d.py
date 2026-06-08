#!/usr/bin/env python3
"""test-install-host-gitignore-strategy-d.py — Inv 53 (Strategy D, #1086/#1085).

Strategy D (full-vendor) supersedes Strategy A (#1052/#1060). Under D a vendored
install tracks the WHOLE `.rabbit/` in the host repo — BOTH the tool tree
(`.rabbit/.claude/`) AND the work (`.rabbit/rabbit-project/`) — ignoring ONLY the
ephemerals (`.rabbit/.runtime/`, plus whatever the inner `.rabbit/.gitignore`
covers). This makes vendored == standalone for VCS: a worktree of the host repo
is self-contained (tool+work at consistent paths) so the proven standalone
machinery works unchanged.

This reverses #1052's A-shape, which ALSO ignored `.rabbit/.claude/`. The
installer MUST migrate an existing A-shape host `.gitignore` (drop the
`.rabbit/.claude` ignore line, keep ephemerals ignored) and a legacy blanket
`.rabbit/` ignore to the D-shape.

This test pins, against the REAL installer helper `install.write_host_gitignore`:

  (a) a FRESH host (no `.gitignore`) → the host `.gitignore` ignores ONLY
      `.rabbit/.runtime/`, and does NOT ignore `.rabbit/.claude/...` (TRACKED)
      nor `.rabbit/rabbit-project/...` (TRACKED) — verified via `git check-ignore`
      against a real git repo;
  (b) a host with an A-shape gitignore (the #1052 form: ignore `.rabbit/.claude/`
      + `.rabbit/.runtime/`) is MIGRATED to D — the `.rabbit/.claude` ignore line
      is REMOVED so the tool tree becomes tracked again; ephemerals stay ignored;
  (c) a host with a blanket `.rabbit/` ignore is MIGRATED to D — the blanket line
      is gone, tool + project tracked, ephemerals ignored, unrelated entries kept;
  (d) re-running the helper is IDEMPOTENT (content converges, no growth); a
      STANDALONE install (dst_root NOT named `.rabbit`) leaves the host
      `.gitignore` untouched (host-gitignore management is vendored-only).
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

# Paths the host repo MUST keep tracked / MUST ignore under Strategy D.
TRACKED_PROJECT_PATH = ".rabbit/rabbit-project/features/x/docs/spec.md"
TRACKED_TOOL_PATH = ".rabbit/.claude/settings.json"
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


def test_fresh_host_d_shaped_ignore():
    """A fresh host with no .gitignore gets the D-shaped set: ONLY ephemerals
    ignored; tool tree AND rabbit-project tracked."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        _git(host, "init", "-q")
        dst_root = host / ".rabbit"
        dst_root.mkdir()

        mod.write_host_gitignore(dst_root)

        gi = host / ".gitignore"
        assert gi.is_file(), "host .gitignore must be created"

        assert _is_ignored(host, IGNORED_RUNTIME_PATH), (
            ".rabbit/.runtime/ must be ignored")
        assert not _is_ignored(host, TRACKED_TOOL_PATH), (
            ".rabbit/.claude/ must NOT be ignored (Strategy D — tool tracked); "
            f"git ignored {TRACKED_TOOL_PATH!r}")
        assert not _is_ignored(host, TRACKED_PROJECT_PATH), (
            ".rabbit/rabbit-project/ must NOT be ignored (Strategy D); "
            f"git ignored {TRACKED_PROJECT_PATH!r}")
    print("PASS test_fresh_host_d_shaped_ignore")


def test_a_shape_migrated_to_d():
    """A host carrying the #1052 A-shape (ignore `.rabbit/.claude/` +
    `.rabbit/.runtime/`) is MIGRATED to D: the `.rabbit/.claude` ignore line is
    REMOVED so the tool tree is tracked again; ephemerals stay ignored."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        _git(host, "init", "-q")
        # Pre-existing A-shape host gitignore plus an unrelated user entry.
        (host / ".gitignore").write_text(
            "node_modules/\n"
            "# rabbit vendored install — ignore the tool tree and ephemerals,"
            " NOT rabbit-project (Strategy A, #1052)\n"
            ".rabbit/.claude/\n"
            ".rabbit/.runtime/\n"
            "*.log\n"
        )
        dst_root = host / ".rabbit"
        dst_root.mkdir()

        mod.write_host_gitignore(dst_root)

        content = (host / ".gitignore").read_text()
        lines = [ln.strip() for ln in content.splitlines()]
        # The A-shape tool-tree ignore is gone (migrated to D).
        assert ".rabbit/.claude/" not in lines, (
            "A-shape `.rabbit/.claude/` ignore must be MIGRATED away under D; "
            f"got lines {lines}")
        # Unrelated user entries are preserved.
        assert "node_modules/" in lines, "unrelated entry must be preserved"
        assert "*.log" in lines, "unrelated entry must be preserved"

        # Behavioural consequence: tool tree tracked, ephemerals still ignored.
        assert _is_ignored(host, IGNORED_RUNTIME_PATH), (
            ".rabbit/.runtime/ must remain ignored after A->D migration")
        assert not _is_ignored(host, TRACKED_TOOL_PATH), (
            "after A->D migration .rabbit/.claude/ must NOT be ignored")
        assert not _is_ignored(host, TRACKED_PROJECT_PATH), (
            "after A->D migration .rabbit/rabbit-project/ must NOT be ignored")
    print("PASS test_a_shape_migrated_to_d")


def test_blanket_ignore_migrated_to_d():
    """A host carrying a legacy blanket `.rabbit/` ignore is MIGRATED to the
    D-shape: the over-broad line is gone, tool + project tracked, ephemerals
    ignored, unrelated entries preserved."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        _git(host, "init", "-q")
        (host / ".gitignore").write_text(
            "node_modules/\n"
            ".rabbit/\n"
            "*.log\n"
        )
        dst_root = host / ".rabbit"
        dst_root.mkdir()

        mod.write_host_gitignore(dst_root)

        content = (host / ".gitignore").read_text()
        lines = [ln.strip() for ln in content.splitlines()]
        assert ".rabbit/" not in lines, (
            "blanket `.rabbit/` ignore must be MIGRATED away under D; "
            f"got lines {lines}")
        assert "node_modules/" in lines, "unrelated entry must be preserved"
        assert "*.log" in lines, "unrelated entry must be preserved"

        assert _is_ignored(host, IGNORED_RUNTIME_PATH), (
            ".rabbit/.runtime/ must be ignored after blanket->D migration")
        assert not _is_ignored(host, TRACKED_TOOL_PATH), (
            "after blanket->D migration .rabbit/.claude/ must NOT be ignored")
        assert not _is_ignored(host, TRACKED_PROJECT_PATH), (
            "after blanket->D migration .rabbit/rabbit-project/ must NOT be ignored")
    print("PASS test_blanket_ignore_migrated_to_d")


def test_idempotent_on_rerun():
    """Re-running the helper converges: the host .gitignore content is stable
    and does not grow on a second invocation; the D token is not duplicated."""
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
        assert second.count(".rabbit/.runtime/") == 1, (
            f"token '.rabbit/.runtime/' must appear exactly once; got {second!r}")
        # The tool-tree ignore must NOT have crept back in.
        assert ".rabbit/.claude/" not in [
            ln.strip() for ln in second.splitlines()], (
            f"D-shape must never re-add the `.rabbit/.claude/` ignore; got {second!r}")
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
    test_fresh_host_d_shaped_ignore()
    test_a_shape_migrated_to_d()
    test_blanket_ignore_migrated_to_d()
    test_idempotent_on_rerun()
    test_standalone_install_untouched()
    return 0


if __name__ == "__main__":
    sys.exit(main())
