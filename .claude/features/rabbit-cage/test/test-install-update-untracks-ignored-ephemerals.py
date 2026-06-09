#!/usr/bin/env python3
"""test-install-update-untracks-ignored-ephemerals.py — #1137.

Follow-up from #1135. `write_rabbit_gitignore()` writes the inner
`.rabbit/.gitignore` ephemeral ignore list. When a NEW ephemeral is added to
that list (e.g. `.rabbit-prompt-counter` in #1135), gitignore alone does NOT
untrack a file that an existing vendored host repo already committed — so those
installs keep churning the now-ignored file until a human runs
`git rm --cached .rabbit/<file>`.

`--update` self-heals: `install.untrack_ignored_rabbit_ephemerals(dst_root)`
runs `git rm --cached` (index-only — file stays on disk) for every file
TRACKED under `.rabbit/` that now MATCHES the inner ignore list, so existing
Strategy D full-vendor installs converge on update with no manual step.

This test pins, against the REAL installer helper:

  (a) a vendored host repo that already TRACKS `.rabbit/.rabbit-prompt-counter`
      (now in the ephemeral ignore list) plus a tracked NON-ephemeral file
      (`.rabbit/.claude/settings.json`) -> after the untrack step the ephemeral
      is no longer in `git ls-files` BUT still exists on disk, and the
      non-ephemeral file is left tracked & untouched;
  (b) no-op safety: a repo whose tracked `.rabbit/` files are all
      non-ephemeral -> the helper removes nothing and exits clean;
  (c) degrade-to-no-op: a standalone (non-`.rabbit`) dst_root, and a dst_root
      that is not inside any git repo, both no-op without error.
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

EPHEMERAL_REL = ".rabbit/.rabbit-prompt-counter"
NON_EPHEMERAL_REL = ".rabbit/.claude/settings.json"


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


def _tracked(host: Path) -> set[str]:
    res = _git(host, "ls-files")
    return {ln for ln in res.stdout.splitlines() if ln}


def _make_vendored_host(td: Path, mod) -> tuple[Path, Path]:
    """A vendored host repo with the inner `.rabbit/.gitignore` written and an
    ephemeral + a non-ephemeral file committed under `.rabbit/`."""
    host = (td / "host").resolve()
    host.mkdir()
    _git(host, "init", "-q")
    dst_root = host / ".rabbit"
    (dst_root / ".claude").mkdir(parents=True)
    # Inner ignore list (source-of-truth) written by the real helper.
    mod.write_rabbit_gitignore(dst_root)
    (host / EPHEMERAL_REL).write_text("3\n")
    (host / NON_EPHEMERAL_REL).write_text("{}\n")
    # Force-add the ephemeral so it is TRACKED despite the inner ignore (this is
    # exactly the pre-#1135 vendored state we must self-heal).
    _git(host, "add", "-f", EPHEMERAL_REL, NON_EPHEMERAL_REL)
    _git(host, "add", ".rabbit/.gitignore")
    _git(host, "commit", "-q", "-m", "seed")
    return host, dst_root


def test_untracks_ignored_ephemeral_keeps_disk_and_non_ephemeral():
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host, dst_root = _make_vendored_host(Path(td), mod)

        before = _tracked(host)
        assert EPHEMERAL_REL in before, "setup: ephemeral must start TRACKED"
        assert NON_EPHEMERAL_REL in before, "setup: non-ephemeral must start TRACKED"

        mod.untrack_ignored_rabbit_ephemerals(dst_root)

        after = _tracked(host)
        assert EPHEMERAL_REL not in after, (
            f"{EPHEMERAL_REL} must be UNTRACKED after the --update self-heal; "
            f"still tracked: {sorted(after)}")
        assert (host / EPHEMERAL_REL).is_file(), (
            "git rm --cached must be index-only: the file MUST remain on disk")
        assert NON_EPHEMERAL_REL in after, (
            f"non-ephemeral {NON_EPHEMERAL_REL} must stay tracked; got {sorted(after)}")
    print("PASS test_untracks_ignored_ephemeral_keeps_disk_and_non_ephemeral")


def test_no_op_when_nothing_matches():
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        host = (Path(td) / "host").resolve()
        host.mkdir()
        _git(host, "init", "-q")
        dst_root = host / ".rabbit"
        (dst_root / ".claude").mkdir(parents=True)
        mod.write_rabbit_gitignore(dst_root)
        (host / NON_EPHEMERAL_REL).write_text("{}\n")
        _git(host, "add", NON_EPHEMERAL_REL, ".rabbit/.gitignore")
        _git(host, "commit", "-q", "-m", "seed")

        before = _tracked(host)
        mod.untrack_ignored_rabbit_ephemerals(dst_root)
        after = _tracked(host)
        assert before == after, (
            f"no tracked file matches the ignore list -> must be a no-op; "
            f"before={sorted(before)} after={sorted(after)}")
    print("PASS test_no_op_when_nothing_matches")


def test_standalone_and_non_repo_degrade_to_no_op():
    mod = _load_install()
    # Standalone dst_root (not named `.rabbit`): no-op, no error.
    with tempfile.TemporaryDirectory() as td:
        host = (Path(td) / "host").resolve()
        host.mkdir()
        _git(host, "init", "-q")
        mod.untrack_ignored_rabbit_ephemerals(host)  # must not raise

    # dst_root not inside any git repo: no-op, no error.
    with tempfile.TemporaryDirectory() as td:
        dst_root = (Path(td) / ".rabbit").resolve()
        dst_root.mkdir()
        mod.untrack_ignored_rabbit_ephemerals(dst_root)  # must not raise
    print("PASS test_standalone_and_non_repo_degrade_to_no_op")


def main() -> int:
    test_untracks_ignored_ephemeral_keeps_disk_and_non_ephemeral()
    test_no_op_when_nothing_matches()
    test_standalone_and_non_repo_degrade_to_no_op()
    return 0


if __name__ == "__main__":
    sys.exit(main())
