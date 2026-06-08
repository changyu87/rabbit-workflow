#!/usr/bin/env python3
"""Issue #1112: vendored create-branch must REFUSE to build a toolless worktree.

Strategy D (#1086) assumes the WHOLE `.rabbit/` is tracked, so a worktree of
the host repo is self-contained. On a fresh vendored install where `.rabbit/`
is present on disk but UNTRACKED (gitignored, not yet committed), the precondition
is unmet: `git worktree add ... HEAD` produces a worktree with NO `.rabbit/`
inside it (a toolless worktree). create-branch previously returned exit 0 with a
worktree path that had no vendored tool, and the dispatcher — still cwd'd in the
original main-tree `.rabbit/` — then ran commit-spec, which committed the spec
onto the host's shared `main` HEAD. Silent main pollution; the feature branch
stayed empty.

End-to-end checks (real temp git repos, real subprocess invocations):

  * VENDORED create-branch FAILS LOUDLY (non-zero exit, actionable message)
    when `.rabbit/` is NOT tracked at HEAD, instead of emitting a toolless
    worktree path. No worktree and no JSON result are produced.
  * VENDORED commit-spec REFUSES to commit onto the host's shared main HEAD
    when a per-session worktree exists but the command is run from the
    original main-tree `.rabbit/` cwd. The host HEAD is NOT moved.
  * VENDORED commit-spec run from INSIDE the per-session worktree still works
    (the guard fires only on the host's shared main-worktree HEAD).
  * STANDALONE is UNAFFECTED: commit-spec commits normally; there is no
    per-session worktree and no untracked-.rabbit precondition.

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


def _vendored_runtime(rabbit: Path) -> None:
    runtime = rabbit / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "mode").write_text("vendored", encoding="utf-8")


def _vendored_host_tracked(root: Path) -> Path:
    """Strategy-D host: the WHOLE `.rabbit/` is tracked at HEAD. Returns .rabbit."""
    _git_init_commit(root)
    rabbit = root / ".rabbit"
    _vendored_runtime(rabbit)
    (rabbit / ".claude").mkdir(parents=True)
    (rabbit / ".claude/marker").write_text("tool\n", encoding="utf-8")
    feat = rabbit / "rabbit-project/features/demo/docs"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("v1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: vendored install (Strategy D)")
    return rabbit


def _vendored_host_untracked(root: Path) -> Path:
    """Fresh vendored install: `.rabbit/` is on disk but gitignored/UNTRACKED.

    HEAD carries only README + .gitignore — NOT `.rabbit/`. Returns .rabbit.
    """
    _git_init_commit(root)
    (root / "README.md").write_text("host\n", encoding="utf-8")
    (root / ".gitignore").write_text(".rabbit/\n", encoding="utf-8")
    rabbit = root / ".rabbit"
    _vendored_runtime(rabbit)
    (rabbit / ".claude").mkdir(parents=True)
    (rabbit / ".claude/marker").write_text("tool\n", encoding="utf-8")
    feat = rabbit / "rabbit-project/features/demo/docs"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("v1\n", encoding="utf-8")
    # Only README + .gitignore are committed; .rabbit/ stays untracked.
    _git(root, "add", "README.md", ".gitignore")
    _git(root, "commit", "-q", "-m", "base: host without tracked .rabbit/")
    return rabbit


def _parse(proc: subprocess.CompletedProcess) -> dict:
    assert proc.returncode == 0, f"create-branch failed: {proc.stderr}"
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# create-branch precondition: refuse a toolless worktree.
# ---------------------------------------------------------------------------
def test_vendored_create_branch_fails_when_rabbit_untracked() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host_untracked(root)

        proc = _run(rabbit_cwd, "create-branch", "demo", "add a thing")
        assert proc.returncode != 0, (
            "create-branch MUST fail when .rabbit/ is untracked at HEAD "
            f"(got exit 0, stdout={proc.stdout!r})")
        # Actionable message naming the unmet precondition.
        msg = (proc.stderr + proc.stdout).lower()
        assert ".rabbit" in msg and "commit" in msg, (
            f"failure message must be actionable: {proc.stderr!r}")
        # No worktree was created.
        wt_root = root / ".rabbit-worktrees"
        assert not wt_root.exists() or not any(wt_root.iterdir()), (
            "a toolless worktree was created despite the unmet precondition")
        # No JSON result leaked to stdout.
        assert not proc.stdout.strip().startswith("{"), (
            f"create-branch emitted a result despite failing: {proc.stdout!r}")


def test_vendored_create_branch_succeeds_when_rabbit_tracked() -> None:
    """The Strategy-D happy path still works: tracked .rabbit/ -> worktree."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host_tracked(root)
        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "tracked ok"))
        assert out["mode"] == "vendored", out
        wt = Path(out["worktree"])
        assert (wt / ".rabbit/.claude/marker").is_file(), (
            "tracked .rabbit/ must yield a self-contained worktree")


# ---------------------------------------------------------------------------
# commit-spec guard: never commit onto the host's shared main HEAD when a
# per-session worktree exists.
# ---------------------------------------------------------------------------
def test_vendored_commit_spec_refuses_host_head_when_worktree_exists() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host_tracked(root)
        host_head_before = _git(root, "rev-parse", "HEAD").stdout.strip()

        # Create a per-session worktree (the normal Strategy-D create-branch).
        _parse(_run(rabbit_cwd, "create-branch", "demo", "guard test"))

        # The dispatcher is STILL in the original main-tree .rabbit/ cwd and
        # edits the spec there, then mistakenly calls commit-spec from here.
        spec = rabbit_cwd / "rabbit-project/features/demo/docs/spec.md"
        spec.write_text("v2 leaked\n", encoding="utf-8")
        cs = _run(rabbit_cwd, "commit-spec", "demo", "guard test")

        assert cs.returncode != 0, (
            "commit-spec MUST refuse to commit onto the host shared main HEAD "
            f"while a per-session worktree exists (got exit 0: {cs.stdout!r})")
        # Host shared HEAD was NOT moved — no silent main pollution.
        assert _git(root, "rev-parse", "HEAD").stdout.strip() == host_head_before, (
            "commit-spec committed onto the host's shared main HEAD — #1112 pollution")
        msg = (cs.stderr + cs.stdout).lower()
        assert "worktree" in msg, (
            f"refusal must point at the worktree: {cs.stderr!r}")


def test_vendored_commit_spec_works_inside_worktree() -> None:
    """The guard fires only on the host shared HEAD; inside the per-session
    worktree commit-spec still commits normally onto the feature branch."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host_tracked(root)
        host_head_before = _git(root, "rev-parse", "HEAD").stdout.strip()

        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "inside wt"))
        wt = Path(out["worktree"])
        wt_rabbit = wt / ".rabbit"

        spec = wt_rabbit / "rabbit-project/features/demo/docs/spec.md"
        spec.write_text("v2 inside\n", encoding="utf-8")
        cs = _run(wt_rabbit, "commit-spec", "demo", "inside wt")
        assert cs.returncode == 0, (
            f"commit-spec must work from inside the worktree: {cs.stderr}")

        # Feature branch advanced; host shared HEAD unchanged.
        count = _git(
            wt, "rev-list", "--count", f"{host_head_before}..HEAD"
        ).stdout.strip()
        assert count == "1", f"expected 1 spec commit on feature branch, got {count}"
        assert _git(root, "rev-parse", "HEAD").stdout.strip() == host_head_before


def test_standalone_commit_spec_unaffected() -> None:
    """Standalone mode has no per-session worktree and no untracked-.rabbit
    precondition: commit-spec commits normally."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init_commit(root)
        (root / ".claude/features/demo/docs").mkdir(parents=True)
        (root / ".claude/features/demo/docs/spec.md").write_text("v1\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")
        head_before = _git(root, "rev-parse", "HEAD").stdout.strip()

        (root / ".claude/features/demo/docs/spec.md").write_text("v2\n", encoding="utf-8")
        cs = _run(root, "commit-spec", "demo", "standalone change")
        assert cs.returncode == 0, f"standalone commit-spec must work: {cs.stderr}"
        assert _git(root, "rev-parse", "HEAD").stdout.strip() != head_before, (
            "standalone commit-spec must advance HEAD")


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
