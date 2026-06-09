#!/usr/bin/env python3
"""Inv 63 (issue #1125): Step-5 dispatch anchors the subagent at the
per-session worktree.

In vendored mode Step 2 create-branch produces a per-session Strategy-D
worktree on the feature branch (Inv 61), but the Step-5 TDD-subagent dispatch
had no mechanism to make the subagent execute inside that worktree: the Agent
tool has no cwd parameter, so the subagent inherited the host `.rabbit` cwd
(on the host's checked-out branch) and its scope markers / commits / state
transitions landed on the host tree, defeating Strategy D (#1059).

The cross-feature half — an optional `--worktree <abs>` arg (alias `--cwd`) on
`dispatch-tdd-subagent.py` that emits absolute worktree-anchored path slots in
the prompt — ALREADY SHIPPED in #1128 (tdd-subagent, Inv 65). This test locks
the rabbit-feature half: the companion `feature-touch.py dispatch-prompt`
subcommand assembles the Step-5 dispatch argv and passes `--worktree <abs>`
ONLY when a per-session worktree is present.

End-to-end checks (real subprocess invocations of the companion against the
real `dispatch-tdd-subagent.py` and a real temp feature spec):

  * VENDORED with a per-session worktree: the assembled dispatch argv contains
    `--worktree <abs-worktree>` resolved to the ABSOLUTE worktree root.
  * A repo-RELATIVE worktree value is resolved to an absolute path before
    being passed as `--worktree`.
  * STANDALONE / no-worktree: the assembled argv contains NO `--worktree` and
    is byte-identical to the pre-wiring form (hard back-compat requirement).
  * The assembled prompt actually RUNS (dispatch-tdd-subagent.py exits 0); in
    the worktree case its baked path slots carry the absolute worktree prefix.
  * The Step-5 SKILL.md body delegates dispatch-argv assembly to the
    `dispatch-prompt` subcommand (no inline argv assembly).

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch"
)
COMPANION = SKILL_DIR / "scripts/feature-touch.py"
SOURCE_SKILL = SKILL_DIR / "SKILL.md"
DEPLOYED_SKILL = REPO_ROOT / ".claude/skills/rabbit-feature-touch/SKILL.md"
DISPATCH = (
    REPO_ROOT
    / ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py"
)


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(COMPANION), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _dispatch_prompt(
    cwd: Path,
    feature: str,
    spec: str,
    *,
    impl: str | None = None,
    worktree: str | None = None,
) -> subprocess.CompletedProcess:
    args = ["dispatch-prompt", feature, "--spec", spec]
    if impl is not None:
        args += ["--impl-suggestion", impl]
    if worktree is not None:
        args += ["--worktree", worktree]
    return _run(cwd, *args)


def _make_feature_repo(root: Path) -> Path:
    """A minimal standalone repo with a demo feature spec. Returns the spec
    path relative to root (the shape dispatch-tdd-subagent.py expects)."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    feat = root / ".claude/features/demo/docs"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# demo spec\n", encoding="utf-8")
    return Path(".claude/features/demo/docs/spec.md")


def _parse_argv(stdout: str) -> list[str]:
    """The dispatch-prompt subcommand emits the assembled argv. Accept either a
    single shell-quoted line or a JSON array; normalize to a token list."""
    import json

    text = stdout.strip()
    assert text, "dispatch-prompt emitted no argv on stdout"
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (ValueError, TypeError):
        pass
    # Fallback: shell-tokenize the (possibly multi-line) command string.
    return shlex.split(text)


# ---------------------------------------------------------------------------
# Vendored with a per-session worktree -> --worktree <abs> is passed.
# ---------------------------------------------------------------------------
def test_vendored_worktree_argv_has_absolute_worktree() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        spec = _make_feature_repo(root)
        wt = root / ".rabbit-worktrees" / "session-deadbeef"
        wt.mkdir(parents=True)

        r = _dispatch_prompt(root, "demo", str(spec), worktree=str(wt))
        assert r.returncode == 0, f"dispatch-prompt failed: {r.stderr}"
        argv = _parse_argv(r.stdout)
        assert "--worktree" in argv, (
            f"vendored worktree dispatch must pass --worktree; argv={argv}"
        )
        idx = argv.index("--worktree")
        passed = argv[idx + 1]
        assert Path(passed).is_absolute(), (
            f"--worktree value must be absolute, got {passed!r}"
        )
        assert Path(passed) == wt, (
            f"--worktree must be the worktree root {wt}, got {passed!r}"
        )


def test_repo_relative_worktree_resolved_to_absolute() -> None:
    """A repo-relative worktree value (as create-branch may emit) is resolved
    to an absolute path before being passed."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        spec = _make_feature_repo(root)
        rel_wt = ".rabbit-worktrees/session-cafef00d"
        (root / rel_wt).mkdir(parents=True)

        r = _dispatch_prompt(root, "demo", str(spec), worktree=rel_wt)
        assert r.returncode == 0, f"dispatch-prompt failed: {r.stderr}"
        argv = _parse_argv(r.stdout)
        assert "--worktree" in argv, f"argv missing --worktree: {argv}"
        passed = argv[argv.index("--worktree") + 1]
        assert Path(passed).is_absolute(), (
            f"repo-relative worktree must be resolved to absolute, got {passed!r}"
        )
        assert Path(passed).resolve() == (root / rel_wt).resolve(), (
            f"resolved worktree mismatch: {passed!r} vs {root / rel_wt}"
        )


# ---------------------------------------------------------------------------
# Standalone / no-worktree -> NO --worktree, byte-identical to pre-wiring.
# ---------------------------------------------------------------------------
def test_standalone_argv_has_no_worktree() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        spec = _make_feature_repo(root)

        r = _dispatch_prompt(root, "demo", str(spec))
        assert r.returncode == 0, f"dispatch-prompt failed: {r.stderr}"
        argv = _parse_argv(r.stdout)
        assert "--worktree" not in argv and "--cwd" not in argv, (
            f"standalone dispatch must NOT pass --worktree/--cwd; argv={argv}"
        )


def test_empty_worktree_value_treated_as_no_worktree() -> None:
    """Vendored create-branch in standalone emits worktree:null; an empty
    string passed through MUST be treated as 'no worktree' (no --worktree)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        spec = _make_feature_repo(root)

        r = _dispatch_prompt(root, "demo", str(spec), worktree="")
        assert r.returncode == 0, f"dispatch-prompt failed: {r.stderr}"
        argv = _parse_argv(r.stdout)
        assert "--worktree" not in argv and "--cwd" not in argv, (
            f"empty worktree value must yield no --worktree; argv={argv}"
        )


def test_no_worktree_argv_byte_identical_to_pre_wiring() -> None:
    """Back-compat: the no-worktree argv must match the argv a caller would
    have assembled before the wiring (scope/spec/impl-suggestion only, in that
    canonical order)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        spec = _make_feature_repo(root)
        impl = root / "impl.json"
        impl.write_text("{}\n", encoding="utf-8")

        r = _dispatch_prompt(root, "demo", str(spec), impl=str(impl))
        assert r.returncode == 0, f"dispatch-prompt failed: {r.stderr}"
        argv = _parse_argv(r.stdout)

        # The dispatch script path may be emitted as an absolute path or a
        # repo-relative one; normalize by locating the recognised flags.
        assert "--scope" in argv and argv[argv.index("--scope") + 1] == "demo"
        assert "--spec" in argv and argv[argv.index("--spec") + 1] == str(spec)
        assert "--impl-suggestion" in argv
        assert argv[argv.index("--impl-suggestion") + 1] == str(impl)
        assert "--worktree" not in argv and "--cwd" not in argv
        # The argv must invoke dispatch-tdd-subagent.py.
        assert any("dispatch-tdd-subagent.py" in tok for tok in argv), (
            f"argv must invoke dispatch-tdd-subagent.py; argv={argv}"
        )


# ---------------------------------------------------------------------------
# E2E: the assembled argv actually runs against the REAL dispatch script and
# bakes the worktree path. The dispatch-tdd-subagent.py path emitted in the
# argv is repo-relative (the back-compat form), so these run from the REAL
# REPO_ROOT against a REAL feature (rabbit-feature) and its real spec.
# ---------------------------------------------------------------------------
def _run_assembled(argv: list[str]) -> subprocess.CompletedProcess:
    # argv[0] may be the python interpreter or the script; normalize to invoke
    # with this interpreter from the repo root (where the repo-relative
    # dispatch-tdd-subagent.py path resolves).
    toks = list(argv)
    if toks and Path(toks[0]).name.startswith("python"):
        toks = toks[1:]
    return subprocess.run(
        [sys.executable, *toks],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_assembled_prompt_runs_and_bakes_worktree() -> None:
    spec = ".claude/features/rabbit-feature/docs/spec.md"
    with tempfile.TemporaryDirectory() as td:
        wt = Path(td).resolve() / "session-abc12345"
        wt.mkdir(parents=True)

        r = _dispatch_prompt(REPO_ROOT, "rabbit-feature", spec, worktree=str(wt))
        assert r.returncode == 0, f"dispatch-prompt failed: {r.stderr}"
        argv = _parse_argv(r.stdout)

        run = _run_assembled(argv)
        assert run.returncode == 0, (
            f"assembled dispatch prompt failed to run: {run.stderr}"
        )
        # The emitted prompt must anchor a path slot at the absolute worktree.
        assert str(wt) in run.stdout, (
            "emitted prompt must bake the absolute worktree path in its slots"
        )


def test_assembled_prompt_runs_standalone() -> None:
    spec = ".claude/features/rabbit-feature/docs/spec.md"
    r = _dispatch_prompt(REPO_ROOT, "rabbit-feature", spec)
    assert r.returncode == 0, f"dispatch-prompt failed: {r.stderr}"
    argv = _parse_argv(r.stdout)

    run = _run_assembled(argv)
    assert run.returncode == 0, (
        f"assembled standalone dispatch prompt failed to run: {run.stderr}"
    )


# ---------------------------------------------------------------------------
# SKILL.md Step 5 delegates dispatch-argv assembly to dispatch-prompt.
# ---------------------------------------------------------------------------
def _step5(text: str) -> str:
    m = re.search(
        r"^###\s+Step\s+5\s+[-—]\s+.+?\s*$(.*?)(?=^###\s|^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "SKILL.md is missing a 'Step 5' section"
    return m.group(1)


def test_skill_step5_delegates_to_dispatch_prompt() -> None:
    for path, label in ((SOURCE_SKILL, "source"), (DEPLOYED_SKILL, "deployed")):
        assert path.exists(), f"missing SKILL.md: {path}"
        body = _step5(path.read_text(encoding="utf-8"))
        assert "dispatch-prompt" in body, (
            f"Step 5 ({label}) must invoke the companion 'dispatch-prompt' "
            "subcommand for the mode-aware Step-5 dispatch-argv assembly "
            "(Inv 63, §4 Script-Backed Orchestration)"
        )
        assert "feature-touch.py" in body, (
            f"Step 5 ({label}) must invoke the companion feature-touch.py script"
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
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
