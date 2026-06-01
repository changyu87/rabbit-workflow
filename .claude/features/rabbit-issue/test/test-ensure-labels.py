"""Tests for scripts/_gh.py shared helpers.

Covers ensure_labels idempotency and require_managed safety guard.
Repo-slug resolution is covered by test-gh-helper-resolves-rabbit-repo.py.
"""
import importlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _fresh_gh():
    """Drop cached _gh so per-test PATH/env changes take effect."""
    sys.modules.pop("_gh", None)
    import _gh  # noqa: F401
    return importlib.import_module("_gh")


def test_ensure_labels_calls_gh_label_create(gh_shim, fake_repo):
    gh = _fresh_gh()
    gh.ensure_labels(["bug", "rabbit-managed", "feature:foo", "priority:high"])
    log = gh_shim.read_text().strip().split("\n")
    creates = [line for line in log if line.startswith("label create")]
    assert len(creates) == 4


def test_ensure_labels_idempotent_on_duplicate(gh_shim, fake_repo, monkeypatch):
    monkeypatch.setenv("GH_SHIM_LABEL_CREATE_EXIT", "1")
    gh = _fresh_gh()
    # MUST NOT raise even though gh exits 1 (duplicate label).
    gh.ensure_labels(["bug"])


def test_require_managed_raises_on_unmanaged(gh_shim, fake_repo, tmp_path, monkeypatch):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({"number": 1, "labels": [{"name": "bug"}]}))
    monkeypatch.setenv("GH_SHIM_ISSUE_BODY", str(body))
    gh = _fresh_gh()
    with pytest.raises(SystemExit):
        gh.require_managed(1)


def test_require_managed_passes_when_label_present(gh_shim, fake_repo, tmp_path, monkeypatch):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({
        "number": 1,
        "labels": [{"name": "bug"}, {"name": "rabbit-managed"}],
    }))
    monkeypatch.setenv("GH_SHIM_ISSUE_BODY", str(body))
    gh = _fresh_gh()
    gh.require_managed(1)  # no exception


def test_require_auth_exits_when_gh_unauth(gh_shim, fake_repo, monkeypatch):
    monkeypatch.setenv("GH_SHIM_AUTH_EXIT", "1")
    gh = _fresh_gh()
    with pytest.raises(SystemExit):
        gh.require_auth()


def test_require_auth_passes_when_gh_green(gh_shim, fake_repo):
    gh = _fresh_gh()
    gh.require_auth()  # no exception
