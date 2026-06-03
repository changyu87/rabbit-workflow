#!/usr/bin/env python3
"""Inv 56 (issue #399 Phase 2a): feature-touch.py resolves the flat docs/ layout.

The #399 migration's ratified target is a FLAT per-feature docs/ layout:
docs/spec.md and docs/contract.md (preserving docs/bugs/). During the
coexistence window the companion feature-touch.py resolvers MUST prefer the
flat docs/ location and fall back to the legacy layouts so later file moves do
not break tooling:

  spec     : docs/spec.md  >  specs/spec.md  >  docs/spec/spec.md
  contract : docs/contract.md  >  specs/contract.md  >  docs/spec/contract.md

End-to-end checks (real temp git repos, real subprocess invocations):

  * resolve-spec-path returns docs/spec.md when only the flat docs/ layout
    is present.
  * resolve-spec-path still returns specs/spec.md when only the specs/ layout
    is present (legacy behaviour preserved — fallback always hits today).
  * resolve-spec-path returns docs/spec.md when BOTH layouts coexist
    (docs/ wins).
  * resolve-contract-path mirrors the same preference order.
  * commit-spec stages and commits the resolved spec under the flat docs/
    layout.
  * mode-aware: plugin mode resolves under .rabbit/rabbit-project/features/.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when every rabbit feature has migrated to the flat
docs/ layout and the dual-read fallback to specs/ and docs/spec/ is removed
(issue #399 cleanup).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPANION = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch/scripts/feature-touch.py"
)


def _run(root: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(COMPANION), *args],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)


# ---------------------------------------------------------------------------
# resolve-spec-path: flat docs/ preference order.
# ---------------------------------------------------------------------------
def test_resolve_spec_prefers_flat_docs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        feat = root / ".claude/features/demo/docs"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("flat", encoding="utf-8")
        r = _run(root, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/docs/spec.md", (
            f"expected flat docs/spec.md, got {r.stdout.strip()!r}"
        )


def test_resolve_spec_falls_back_to_specs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        feat = root / ".claude/features/demo/specs"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("legacy specs", encoding="utf-8")
        r = _run(root, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/specs/spec.md", (
            f"expected specs/ fallback, got {r.stdout.strip()!r}"
        )


def test_resolve_spec_falls_back_to_legacy_docs_spec() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        feat = root / ".claude/features/demo/docs/spec"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("legacy docs/spec", encoding="utf-8")
        r = _run(root, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/docs/spec/spec.md", (
            f"expected docs/spec/ fallback, got {r.stdout.strip()!r}"
        )


def test_resolve_spec_flat_docs_wins_when_both_exist() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        feat = root / ".claude/features/demo"
        (feat / "docs").mkdir(parents=True)
        (feat / "specs").mkdir(parents=True)
        (feat / "docs/spec.md").write_text("flat", encoding="utf-8")
        (feat / "specs/spec.md").write_text("legacy", encoding="utf-8")
        r = _run(root, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/docs/spec.md", (
            f"flat docs/ must win when both layouts exist, got {r.stdout.strip()!r}"
        )


# ---------------------------------------------------------------------------
# resolve-contract-path: mirrors the spec preference order.
# ---------------------------------------------------------------------------
def test_resolve_contract_prefers_flat_docs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        feat = root / ".claude/features/demo/docs"
        feat.mkdir(parents=True)
        (feat / "contract.md").write_text("flat", encoding="utf-8")
        r = _run(root, "resolve-contract-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/docs/contract.md", (
            f"expected flat docs/contract.md, got {r.stdout.strip()!r}"
        )


def test_resolve_contract_falls_back_to_specs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        feat = root / ".claude/features/demo/specs"
        feat.mkdir(parents=True)
        (feat / "contract.md").write_text("legacy", encoding="utf-8")
        r = _run(root, "resolve-contract-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/specs/contract.md", (
            f"expected specs/ fallback, got {r.stdout.strip()!r}"
        )


def test_resolve_contract_flat_docs_wins_when_both_exist() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        feat = root / ".claude/features/demo"
        (feat / "docs").mkdir(parents=True)
        (feat / "specs").mkdir(parents=True)
        (feat / "docs/contract.md").write_text("flat", encoding="utf-8")
        (feat / "specs/contract.md").write_text("legacy", encoding="utf-8")
        r = _run(root, "resolve-contract-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".claude/features/demo/docs/contract.md", (
            f"flat docs/ must win when both layouts exist, got {r.stdout.strip()!r}"
        )


# ---------------------------------------------------------------------------
# commit-spec resolves and commits the flat docs/ layout.
# ---------------------------------------------------------------------------
def test_commit_spec_under_flat_docs_layout() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
        feat = root / ".claude/features/demo/docs"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("v1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True)
        # Modify the flat-docs spec, then commit.
        (feat / "spec.md").write_text("v2\n", encoding="utf-8")
        r = _run(root, "commit-spec", "demo", "issue #399 demo")
        assert r.returncode == 0, r.stderr
        log = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--pretty=%s"],
            capture_output=True, text=True,
        ).stdout.strip()
        assert log == "spec(demo): update spec for issue #399 demo", (
            f"commit message mismatch: {log!r}"
        )


# ---------------------------------------------------------------------------
# mode-aware: plugin mode resolves under the plugin feature_dir prefix.
# ---------------------------------------------------------------------------
def test_resolve_spec_plugin_mode_flat_docs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_init(root)
        mode = root / ".rabbit/.runtime"
        mode.mkdir(parents=True)
        (mode / "mode").write_text("plugin", encoding="utf-8")
        feat = root / ".rabbit/rabbit-project/features/demo/docs"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text("flat", encoding="utf-8")
        r = _run(root, "resolve-spec-path", "demo")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == ".rabbit/rabbit-project/features/demo/docs/spec.md", (
            f"plugin-mode flat docs/ resolution mismatch, got {r.stdout.strip()!r}"
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
