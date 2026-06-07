"""Tests for _gh.repo_slug — Fixes #264 resolution order.

Pins the spec invariant (docs/spec.md §Repository discovery):

  rabbit-issue ALWAYS targets the upstream rabbit-workflow repo. The
  repo slug resolves to:
    1. RABBIT_ISSUE_REPO env var when set, else
    2. const RABBIT_REPO_DEFAULT = "changyu87/rabbit-workflow"

  _gh.py NEVER calls `git remote get-url origin`. In particular, a
  cwd that has no .git directory (plugin-install path) MUST still
  resolve cleanly to the default const.
"""
import importlib
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

DEFAULT_SLUG = "changyu87/rabbit-workflow"


def _fresh_gh():
    """Drop cached _gh so per-test env changes take effect on import."""
    sys.modules.pop("_gh", None)
    import _gh  # noqa: F401
    return importlib.import_module("_gh")


def test_repo_slug_default_const(monkeypatch):
    """No env override -> the module-level RABBIT_REPO_DEFAULT const."""
    monkeypatch.delenv("RABBIT_ISSUE_REPO", raising=False)
    gh = _fresh_gh()
    assert gh.RABBIT_REPO_DEFAULT == DEFAULT_SLUG
    assert gh.repo_slug() == DEFAULT_SLUG


def test_repo_slug_env_override(monkeypatch):
    """RABBIT_ISSUE_REPO env var overrides the default const."""
    monkeypatch.setenv("RABBIT_ISSUE_REPO", "myfork/rabbit-workflow")
    gh = _fresh_gh()
    assert gh.repo_slug() == "myfork/rabbit-workflow"


def test_repo_slug_ignores_origin(monkeypatch, tmp_path):
    """In a non-git cwd (plugin-install path), still returns the default.

    This is the regression for #264: previously the resolver shelled out
    to `git remote get-url origin` and either picked up the user's
    project remote (wrong target) or aborted on non-GH origins.
    """
    monkeypatch.delenv("RABBIT_ISSUE_REPO", raising=False)
    monkeypatch.chdir(tmp_path)  # no .git here
    gh = _fresh_gh()
    assert gh.repo_slug() == DEFAULT_SLUG


def test_repo_slug_env_overrides_in_non_git_dir(monkeypatch, tmp_path):
    """Env override works even when cwd has no git repo."""
    monkeypatch.setenv("RABBIT_ISSUE_REPO", "xyz/abc")
    monkeypatch.chdir(tmp_path)
    gh = _fresh_gh()
    assert gh.repo_slug() == "xyz/abc"
