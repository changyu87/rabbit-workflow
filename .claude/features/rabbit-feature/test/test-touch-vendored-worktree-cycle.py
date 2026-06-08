#!/usr/bin/env python3
"""Inv 61 (issues #1087, #1059): vendored feature-touch runs the whole TDD
cycle inside a PER-SESSION git worktree placed OUTSIDE the tracked tree.

Strategy D (#1085) tracks the WHOLE `.rabbit/` in the host repo (shipped by
#1086), so a worktree of the HOST repo is SELF-CONTAINED — it holds both the
tool (`.rabbit/.claude`) AND the work (`.rabbit/rabbit-project`) at consistent
paths, exactly like a standalone worktree. The proven standalone worktree
machinery therefore works unchanged in vendored mode.

The bug being resolved (#1059): in vendored mode the feature-touch git ops
operated on the HOST repo's single shared HEAD, so two concurrent sessions
stomped each other (session A's create-branch then session B's checkout moved
the shared HEAD). Running the cycle in a per-session worktree gives each
session its own HEAD.

End-to-end checks (real temp git repos, real subprocess invocations, real
`git worktree`):

  * VENDORED create-branch creates an isolated per-session worktree of the
    HOST repo OUTSIDE the tracked `.rabbit/` tree, checks the feature branch
    out THERE, and emits machine-readable JSON naming the branch + worktree
    path. The HOST repo's shared HEAD is NOT moved.
  * The worktree is self-contained: the whole tracked `.rabbit/` (tool +
    work) is present at the SAME relative paths inside it.
  * A full vendored cycle inside the worktree (spec-commit -> impl-commit ->
    branch carries commits) lands its commits on the feature branch, not on
    the host's checked-out branch.
  * #1059 regression: TWO concurrent vendored sessions get DISTINCT
    worktrees + branches and do NOT stomp each other's HEAD.
  * STANDALONE create-branch is UNCHANGED: plain `git checkout -b` in the
    current repo (no worktree), emitting JSON with a null worktree.
  * The worktree path is NEVER under `.rabbit/`.

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


def _vendored_host(root: Path) -> Path:
    """Build a Strategy-D vendored host repo under <root>.

    <root> is the HOST git repo. <root>/.rabbit is the vendored install dir
    (the rabbit session cwd) and is FULLY TRACKED (post-#1086): it holds both
    the tool (.rabbit/.claude/...) and the work (.rabbit/rabbit-project/...).
    Returns the .rabbit install dir (the cwd the producer runs from).
    """
    _git_init_commit(root)
    rabbit = root / ".rabbit"
    runtime = rabbit / ".runtime"
    runtime.mkdir(parents=True)
    (runtime / "mode").write_text("vendored", encoding="utf-8")
    # Tool side (consistent path inside any worktree).
    (rabbit / ".claude").mkdir(parents=True)
    (rabbit / ".claude/marker").write_text("tool\n", encoding="utf-8")
    # Work side: a feature with a flat-docs spec.
    feat = rabbit / "rabbit-project/features/demo/docs"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("v1\n", encoding="utf-8")
    # Strategy D: the WHOLE .rabbit/ is tracked.
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: vendored install (Strategy D)")
    return rabbit


def _parse(proc: subprocess.CompletedProcess) -> dict:
    assert proc.returncode == 0, f"create-branch failed: {proc.stderr}"
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Vendored create-branch creates an isolated per-session worktree.
# ---------------------------------------------------------------------------
def test_vendored_create_branch_makes_isolated_worktree() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host(root)
        host_head_before = _git(root, "rev-parse", "HEAD").stdout.strip()
        host_branch_before = _git(
            root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "add a thing"))
        assert out["mode"] == "vendored", out
        assert out["branch"] == "feat/demo-add-a-thing", out
        wt = Path(out["worktree"])

        # The worktree exists and is a real git worktree on the feature branch.
        assert wt.is_dir(), f"worktree dir missing: {wt}"
        wt_branch = _git(wt, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        assert wt_branch == "feat/demo-add-a-thing", (
            f"worktree not on feature branch: {wt_branch!r}")

        # The HOST repo's shared HEAD/branch is UNTOUCHED (#1059 core).
        assert _git(root, "rev-parse", "HEAD").stdout.strip() == host_head_before
        assert _git(
            root, "rev-parse", "--abbrev-ref", "HEAD"
        ).stdout.strip() == host_branch_before, (
            "host shared HEAD was moved — the #1059 stomp")


def test_vendored_worktree_is_outside_rabbit_tree() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host(root)
        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "place it well"))
        wt = Path(out["worktree"]).resolve()
        rabbit_real = rabbit_cwd.resolve()
        assert rabbit_real not in wt.parents and wt != rabbit_real, (
            f"worktree {wt} must NOT live under the tracked .rabbit/ tree "
            f"{rabbit_real}")


def test_vendored_worktree_is_self_contained() -> None:
    """The whole tracked .rabbit/ (tool + work) is present at the SAME relative
    paths inside the worktree — the Strategy-D self-containment property."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host(root)
        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "self contained"))
        wt = Path(out["worktree"])
        assert (wt / ".rabbit/.claude/marker").is_file(), (
            "tool side missing in worktree")
        assert (wt / ".rabbit/rabbit-project/features/demo/docs/spec.md").is_file(), (
            "work side missing in worktree")
        assert (wt / ".rabbit/.runtime/mode").read_text().strip() == "vendored"


def test_vendored_full_cycle_commits_land_on_branch() -> None:
    """A full vendored cycle run inside the worktree: spec-commit then an
    impl-commit. Both commits land on the feature branch in the worktree; the
    host's checked-out branch sees neither."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host(root)
        host_head_before = _git(root, "rev-parse", "HEAD").stdout.strip()

        out = _parse(_run(rabbit_cwd, "create-branch", "demo", "full cycle"))
        wt = Path(out["worktree"])
        # The vendored cwd inside the worktree (where the cycle would run).
        wt_rabbit = wt / ".rabbit"

        # 1) Edit + commit the spec via commit-spec (run from the worktree cwd).
        spec = wt_rabbit / "rabbit-project/features/demo/docs/spec.md"
        spec.write_text("v2 spec\n", encoding="utf-8")
        cs = _run(wt_rabbit, "commit-spec", "demo", "full cycle")
        assert cs.returncode == 0, cs.stderr

        # 2) Simulate an impl-commit (the TDD subagent's work) in the worktree.
        impl = wt_rabbit / "rabbit-project/features/demo/impl.py"
        impl.write_text("print('impl')\n", encoding="utf-8")
        _git(wt, "add", "-f", str(impl))
        _git(wt, "commit", "-q", "-m", "impl(demo): full cycle")

        # The feature branch carries BOTH commits past the base.
        count = _git(
            wt, "rev-list", "--count", f"{host_head_before}..HEAD"
        ).stdout.strip()
        assert count == "2", (
            f"expected 2 commits (spec + impl) on the feature branch, got {count}")

        # The host's shared HEAD is still at base — untouched.
        assert _git(root, "rev-parse", "HEAD").stdout.strip() == host_head_before


def test_two_concurrent_vendored_sessions_do_not_stomp() -> None:
    """#1059 regression: two concurrent vendored sessions each get a DISTINCT
    worktree + branch and never share/stomp the host HEAD."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rabbit_cwd = _vendored_host(root)
        host_head_before = _git(root, "rev-parse", "HEAD").stdout.strip()

        a = _parse(_run(rabbit_cwd, "create-branch", "demo", "session alpha"))
        b = _parse(_run(rabbit_cwd, "create-branch", "demo", "session beta"))

        assert a["branch"] != b["branch"], (
            f"distinct requests must yield distinct branches: {a} {b}")
        assert a["worktree"] != b["worktree"], (
            f"each session must get its own worktree: {a} {b}")

        wt_a, wt_b = Path(a["worktree"]), Path(b["worktree"])
        # Interleave commits: A commits, then B commits — neither sees the
        # other's commit, and the host HEAD never moves.
        (wt_a / ".rabbit/work-a.txt").write_text("a\n", encoding="utf-8")
        _git(wt_a, "add", "-f", ".rabbit/work-a.txt")
        _git(wt_a, "commit", "-q", "-m", "A work")

        (wt_b / ".rabbit/work-b.txt").write_text("b\n", encoding="utf-8")
        _git(wt_b, "add", "-f", ".rabbit/work-b.txt")
        _git(wt_b, "commit", "-q", "-m", "B work")

        # A's branch has work-a but NOT work-b; B's has the reverse.
        assert (wt_a / ".rabbit/work-a.txt").is_file()
        assert not (wt_a / ".rabbit/work-b.txt").exists(), (
            "session B's work leaked into session A's worktree — #1059 stomp")
        assert (wt_b / ".rabbit/work-b.txt").is_file()
        assert not (wt_b / ".rabbit/work-a.txt").exists(), (
            "session A's work leaked into session B's worktree — #1059 stomp")

        # Host HEAD never moved.
        assert _git(root, "rev-parse", "HEAD").stdout.strip() == host_head_before


# ---------------------------------------------------------------------------
# Standalone create-branch is UNCHANGED: plain `git checkout -b`, no worktree.
# ---------------------------------------------------------------------------
def test_standalone_create_branch_unchanged_no_worktree() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init_commit(root)
        (root / ".claude/features/demo/docs").mkdir(parents=True)
        (root / ".claude/features/demo/docs/spec.md").write_text("v1\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

        out = _parse(_run(root, "create-branch", "demo", "standalone path"))
        assert out["mode"] == "standalone", out
        assert out["branch"] == "feat/demo-standalone-path", out
        assert out["worktree"] is None, (
            "standalone mode must NOT create a worktree")
        # The current repo is now ON the feature branch (checkout -b semantics).
        assert _git(
            root, "rev-parse", "--abbrev-ref", "HEAD"
        ).stdout.strip() == "feat/demo-standalone-path"
        # No worktrees beyond the main checkout.
        wl = _git(root, "worktree", "list", "--porcelain").stdout
        assert wl.count("worktree ") == 1, (
            f"standalone must not add a worktree: {wl!r}")


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
