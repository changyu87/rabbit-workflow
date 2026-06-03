#!/usr/bin/env python3
"""Inv 53-55 (issue #440): rabbit-feature-touch SKILL.md §4 authoring standard.

Locks the rabbit-feature-touch SKILL.md (and the deployed copy) against the
spec-rules.md §4 "SKILL.md Authoring Standard":

- Inv 53 Script-Backed Orchestration: the SKILL.md body MUST NOT carry bash
  code fences that contain model-assembled runtime placeholders (e.g.
  `<feature-name>`, `<branch-name>`) combined with control flow. The Step 3
  spec-commit and Step 5 spec-path resolution — both previously inline
  bash blocks with mode-aware branching and `<feature-name>` placeholders —
  MUST now invoke the companion script feature-touch.py instead.

- Inv 54 companion script exists and is script-tier: the companion script
  feature-touch.py exists under the skill's scripts/ dir, is executable,
  exposes the resolve-spec-path and commit-spec subcommands, and owns the
  mode-aware branching + spec-path resolution logic.

- Inv 55 Verbatim Policy Embedding: where the SKILL.md surfaces the
  no-main-session-write / bounded-scope policy in its Red Flags, it cites
  the canonical policy source rather than only paraphrasing. (Light check:
  the Red Flags section names the canonical policy file.)

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch"
)
SOURCE_SKILL = SKILL_DIR / "SKILL.md"
DEPLOYED_SKILL = REPO_ROOT / ".claude/skills/rabbit-feature-touch/SKILL.md"
COMPANION = SKILL_DIR / "scripts/feature-touch.py"

# Placeholder tokens the model would have to assemble at invocation time.
PLACEHOLDER_RE = re.compile(r"<[a-z][a-z0-9-]*>")
# A fenced bash block: ```bash ... ```
BASH_FENCE_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)
# Control-flow tokens that mark an orchestration block (not a single command).
CONTROL_FLOW_RE = re.compile(r"\b(if|then|else|elif|fi|for|while|case)\b")


def _text(path: Path) -> str:
    assert path.exists(), f"missing SKILL.md: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Inv 53: no model-assembled control-flow bash blocks with placeholders.
# ---------------------------------------------------------------------------
def _offending_bash_blocks(text: str) -> list[str]:
    """Return bash blocks that combine a runtime placeholder with control flow.

    Such a block is the §4 violation: a computed/branching orchestration step
    the model assembles inline. Read-only single commands (no control flow)
    and script-invocation commands (the placeholder is a script ARGUMENT,
    not assembled control flow) are allowed.
    """
    offenders = []
    for block in BASH_FENCE_RE.findall(text):
        has_placeholder = PLACEHOLDER_RE.search(block) is not None
        has_control_flow = CONTROL_FLOW_RE.search(block) is not None
        if has_placeholder and has_control_flow:
            offenders.append(block)
    return offenders


def _assert_no_offending_blocks(text: str, label: str) -> None:
    offenders = _offending_bash_blocks(text)
    assert not offenders, (
        f"{label}: found {len(offenders)} bash block(s) combining a runtime "
        "placeholder with control flow — these are §4 Script-Backed "
        "Orchestration violations and MUST move into a companion script. "
        f"First offender:\n{offenders[0][:400]}"
    )


def test_inv53_source_no_offending_bash_blocks() -> None:
    _assert_no_offending_blocks(_text(SOURCE_SKILL), "source SKILL.md")


def test_inv53_deployed_no_offending_bash_blocks() -> None:
    _assert_no_offending_blocks(_text(DEPLOYED_SKILL), "deployed SKILL.md")


def _step_body(text: str, n: int) -> str:
    m = re.search(
        rf"^###\s+Step\s+{n}\s+[-—]\s+.+?\s*$(.*?)(?=^###\s|^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, f"SKILL.md is missing a 'Step {n}' section"
    return m.group(1)


def test_inv53_step3_invokes_companion_commit_spec() -> None:
    for path, label in ((SOURCE_SKILL, "source"), (DEPLOYED_SKILL, "deployed")):
        body = _step_body(_text(path), 3)
        assert "feature-touch.py" in body, (
            f"Step 3 ({label}) must invoke the companion feature-touch.py "
            "script for the mode-aware spec-commit (Inv 53)"
        )
        assert "commit-spec" in body, (
            f"Step 3 ({label}) must invoke the 'commit-spec' subcommand "
            "(Inv 53)"
        )


def test_inv53_step5_invokes_companion_resolve_spec_path() -> None:
    for path, label in ((SOURCE_SKILL, "source"), (DEPLOYED_SKILL, "deployed")):
        body = _step_body(_text(path), 5)
        assert "feature-touch.py" in body, (
            f"Step 5 ({label}) must invoke the companion feature-touch.py "
            "script for spec-path resolution (Inv 53)"
        )
        assert "resolve-spec-path" in body, (
            f"Step 5 ({label}) must invoke the 'resolve-spec-path' subcommand "
            "(Inv 53)"
        )


# ---------------------------------------------------------------------------
# Inv 54: companion script exists, is executable, exposes the subcommands,
# and owns the mode-aware + spec-path-resolution logic.
# ---------------------------------------------------------------------------
def test_inv54_companion_exists_and_executable() -> None:
    assert COMPANION.exists(), f"missing companion script: {COMPANION}"
    assert os.access(COMPANION, os.X_OK), (
        f"companion script must be executable: {COMPANION}"
    )


def test_inv54_companion_usage_lists_subcommands() -> None:
    # No-arg invocation prints usage to stderr and exits 2.
    r = subprocess.run(
        [sys.executable, str(COMPANION)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2, (
        f"no-arg invocation must exit 2 (bad invocation); got {r.returncode}"
    )
    usage = r.stderr
    assert "resolve-spec-path" in usage, "usage must list resolve-spec-path"
    assert "commit-spec" in usage, "usage must list commit-spec"


def test_inv54_companion_owns_mode_branching() -> None:
    src = COMPANION.read_text(encoding="utf-8")
    assert ".rabbit/.runtime/mode" in src, (
        "companion must detect mode from .rabbit/.runtime/mode"
    )
    assert ".rabbit/rabbit-project/features" in src, (
        "companion must own the plugin-mode feature_dir prefix"
    )
    assert ".claude/features" in src, (
        "companion must own the standalone feature_dir prefix"
    )
    assert "git add -f" in src or '"-f"' in src or "'-f'" in src, (
        "companion must own the plugin-mode 'git add -f' staging form"
    )
    assert "specs/spec.md" in src and "docs/spec/spec.md" in src, (
        "companion must own the specs/ preferred + docs/spec/ fallback logic"
    )


def test_inv54_resolve_spec_path_prefers_specs_layout() -> None:
    """E2E: in a temp git repo, resolve-spec-path prefers specs/ then falls
    back to docs/spec/."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        feat = root / ".claude/features/demo"
        # Case A: specs/ layout present -> preferred.
        (feat / "specs").mkdir(parents=True)
        (feat / "specs/spec.md").write_text("x", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(COMPANION), "resolve-spec-path", "demo"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/specs/spec.md", (
            f"expected specs/ layout, got {r.stdout.strip()!r}"
        )
        # Case B: only legacy docs/spec/ present -> fallback.
        feat2 = root / ".claude/features/legacy"
        (feat2 / "docs/spec").mkdir(parents=True)
        (feat2 / "docs/spec/spec.md").write_text("y", encoding="utf-8")
        r2 = subprocess.run(
            [sys.executable, str(COMPANION), "resolve-spec-path", "legacy"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert r2.returncode == 0, r2.stderr
        assert r2.stdout.strip() == ".claude/features/legacy/docs/spec/spec.md", (
            f"expected docs/spec fallback, got {r2.stdout.strip()!r}"
        )


def test_inv54_commit_spec_commits_change_and_skips_noop() -> None:
    """E2E: commit-spec commits a staged spec change, then is a no-op when
    there is nothing to commit."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
        feat = root / ".claude/features/demo/specs"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("v1\n", encoding="utf-8")
        # Need at least one commit for diff --cached to behave; stage + commit base.
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True
        )
        # Modify the spec, then run commit-spec.
        (feat / "spec.md").write_text("v2\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(COMPANION), "commit-spec", "demo", "issue #440 demo"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr
        log = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--pretty=%s"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert log == "spec(demo): update spec for issue #440 demo", (
            f"commit message mismatch: {log!r}"
        )
        # Second run with no change -> no-op (no new commit).
        r2 = subprocess.run(
            [sys.executable, str(COMPANION), "commit-spec", "demo", "again"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert r2.returncode == 0, r2.stderr
        assert "NOOP" in r2.stdout, f"expected NOOP on empty diff, got {r2.stdout!r}"
        count = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert count == "2", f"expected exactly 2 commits (base + spec), got {count}"


# ---------------------------------------------------------------------------
# Inv 55: Verbatim Policy Embedding — Red Flags cite the canonical policy
# source rather than only paraphrasing the bounded-scope / no-main-write rule.
# ---------------------------------------------------------------------------
def test_inv55_red_flags_cite_canonical_policy() -> None:
    for path, label in ((SOURCE_SKILL, "source"), (DEPLOYED_SKILL, "deployed")):
        text = _text(path)
        m = re.search(
            r"^##\s+Red Flags[^\n]*$(.*?)(?=^##\s|\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        assert m, f"{label}: missing '## Red Flags' section"
        body = m.group(1)
        assert "policy/spec-rules.md" in body or "policy/philosophy.md" in body, (
            f"Red Flags ({label}) must cite the canonical policy source "
            "(policy/spec-rules.md or policy/philosophy.md) for the "
            "bounded-scope / no-main-session-write rule rather than only "
            "paraphrasing it (Inv 55, §4 Verbatim Policy Embedding)"
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
