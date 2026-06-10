#!/usr/bin/env python3
"""Issue #1141: vendored worktree feature-touch must NOT misdetect standalone.

The bug: in vendored mode, `create-branch` makes a per-session git worktree via
`git worktree add ... HEAD`. The runtime marker `.rabbit/.runtime/mode` is
EPHEMERAL and gitignored (it is not committed even under Strategy D's
`git add -f .rabbit`), so a `... HEAD` worktree does NOT carry it. Every
subsequent feature-touch script run from `<worktree>/.rabbit` then detected mode
via `<repo_root>/.rabbit/.runtime/mode`, found it ABSENT, and fell back to
STANDALONE — so resolve-spec-path emitted a standalone path, commit-spec looked
under `.claude/features/` and no-op'd, and dispatch-prompt pointed `--spec` at a
nonexistent path.

Fix (structural detection): mode detection treats the presence of the tracked
`<repo_root>/.rabbit/rabbit-project/` work tree as the vendored signal when the
gitignored runtime marker is absent. The work tree IS carried by the worktree
(it is committed), so detection stays self-contained inside the worktree — no
host fallback, no reliance on the ephemeral marker.

End-to-end checks (real temp git repos, real `git worktree`, real subprocess
invocations), with a REALISTIC host `.gitignore` that ignores the ephemeral
`.rabbit/.runtime/`:

  * After create-branch builds the per-session worktree, the worktree does NOT
    contain `.rabbit/.runtime/mode` (the precondition that reproduces the bug).
  * resolve-spec-path run from `<worktree>/.rabbit` resolves the VENDORED spec
    path (cwd-relative, under rabbit-project/), NOT the standalone path.
  * commit-spec run from `<worktree>/.rabbit` force-stages and commits the
    vendored spec onto the feature branch (it does NOT silently no-op).
  * Structural detection from the host `.rabbit/` cwd (marker present) still
    resolves vendored — the marker path and the structural path agree.
  * A pure-standalone repo with NO `.rabbit/rabbit-project/` still resolves
    standalone (structural detection does not over-trigger).

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPANION = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch/scripts/feature-touch.py"
)


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(COMPANION), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
    )


def _git_init_commit(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "checkout", "-q", "-b", "main")


def _realistic_vendored_host(root: Path) -> Path:
    """Build a vendored host repo with a REALISTIC ignore of the ephemeral
    runtime dir.

    <root> is the HOST git repo. <root>/.rabbit is the vendored install dir.
    The whole .rabbit/ work + tool is force-tracked (Strategy D) EXCEPT the
    ephemeral .rabbit/.runtime/, which the host .gitignore excludes. This is
    the realistic shape that reproduces #1141: a `... HEAD` worktree carries
    rabbit-project/ but NOT .runtime/mode.

    Returns the .rabbit install dir (the producer cwd).
    """
    _git_init_commit(root)
    rabbit = root / ".rabbit"
    runtime = rabbit / ".runtime"
    runtime.mkdir(parents=True)
    (runtime / "mode").write_text("vendored", encoding="utf-8")
    # Tool side.
    (rabbit / ".claude").mkdir(parents=True)
    (rabbit / ".claude/marker").write_text("tool\n", encoding="utf-8")
    # Work side: a feature with a flat-docs spec.
    feat = rabbit / "rabbit-project/features/demo/docs"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("v1\n", encoding="utf-8")
    # The ephemeral runtime dir is gitignored, like a real install.
    (root / ".gitignore").write_text(".rabbit/.runtime/\n", encoding="utf-8")
    # Track the tool + work under .rabbit/ (Strategy D) but NOT the ephemeral
    # .rabbit/.runtime/ — exactly like a real vendor commit, so the resulting
    # `... HEAD` worktree carries rabbit-project/ but NOT .runtime/mode. (A
    # blanket `git add -f .rabbit` would override the ignore and force the
    # runtime in too, which is NOT the realistic shape that triggers #1141.)
    _git(root, "add", "-A")
    _git(root, "add", "-f", ".rabbit/.claude", ".rabbit/rabbit-project")
    _git(root, "commit", "-q", "-m", "base: vendored install (runtime ignored)")
    return rabbit


def _parse(proc: subprocess.CompletedProcess) -> dict:
    assert proc.returncode == 0, f"create-branch failed: {proc.stderr}"
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Precondition: the per-session worktree does NOT carry the ephemeral marker.
# ---------------------------------------------------------------------------
def test_worktree_lacks_runtime_mode_marker() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _realistic_vendored_host(root)
        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "no marker"))
        wt = Path(out["worktree"])
        # The bug precondition: the gitignored runtime marker is ABSENT in the
        # worktree (a `... HEAD` worktree only carries committed paths).
        assert not (wt / ".rabbit/.runtime/mode").exists(), (
            "test precondition broken: the worktree should NOT carry the "
            "gitignored .rabbit/.runtime/mode")
        # But the tracked work tree IS present — the structural signal.
        assert (wt / ".rabbit/rabbit-project/features/demo/docs/spec.md").is_file()


# ---------------------------------------------------------------------------
# resolve-spec-path from the worktree resolves VENDORED, not standalone.
# ---------------------------------------------------------------------------
def test_resolve_spec_in_worktree_resolves_vendored() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _realistic_vendored_host(root)
        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "resolve here"))
        wt_rabbit = Path(out["worktree"]) / ".rabbit"
        r = _run(wt_rabbit, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        emitted = r.stdout.strip()
        assert emitted == "rabbit-project/features/demo/docs/spec.md", (
            f"worktree resolve-spec-path misdetected standalone; expected the "
            f"vendored cwd-relative path, got {emitted!r}")
        assert (wt_rabbit / emitted).is_file(), (
            f"emitted path {emitted!r} does not resolve to a file from cwd")


# ---------------------------------------------------------------------------
# commit-spec from the worktree force-stages and commits the vendored spec.
# ---------------------------------------------------------------------------
def test_commit_spec_in_worktree_commits_vendored() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _realistic_vendored_host(root)
        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "commit here"))
        wt = Path(out["worktree"])
        wt_rabbit = wt / ".rabbit"
        spec = wt_rabbit / "rabbit-project/features/demo/docs/spec.md"
        spec.write_text("v2 spec\n", encoding="utf-8")
        cs = _run(wt_rabbit, "commit-spec", "demo", "issue #1141")
        assert cs.returncode == 0, cs.stderr
        assert "NOOP" not in cs.stdout, (
            f"commit-spec misdetected standalone and no-op'd: {cs.stdout!r}")
        log = _git(wt, "log", "-1", "--pretty=%s").stdout.strip()
        assert log == "spec(demo): update spec for issue #1141", (
            f"commit message mismatch / commit missing: {log!r} (stdout={cs.stdout!r})")
        tracked = _git(
            wt, "ls-files", ".rabbit/rabbit-project/features/demo/docs/spec.md"
        ).stdout.strip()
        assert tracked == ".rabbit/rabbit-project/features/demo/docs/spec.md", (
            f"vendored spec not committed on the feature branch; ls-files={tracked!r}")


# ---------------------------------------------------------------------------
# Structural detection from the host cwd (marker present) still vendored.
# ---------------------------------------------------------------------------
def test_resolve_spec_host_cwd_still_vendored() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _realistic_vendored_host(root)
        r = _run(rabbit_cwd, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "rabbit-project/features/demo/docs/spec.md", (
            f"host-cwd vendored resolution regressed, got {r.stdout.strip()!r}")


# ---------------------------------------------------------------------------
# Structural detection does NOT over-trigger: a pure standalone repo with no
# .rabbit/rabbit-project/ still resolves standalone.
# ---------------------------------------------------------------------------
def test_standalone_repo_not_misdetected_vendored() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init_commit(root)
        feat = root / ".claude/features/demo/docs"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("v1\n", encoding="utf-8")
        r = _run(root, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/docs/spec.md", (
            f"standalone repo misdetected vendored, got {r.stdout.strip()!r}")


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
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
