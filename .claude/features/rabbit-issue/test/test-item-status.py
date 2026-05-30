"""E2E tests for scripts/item-status.py (show / close / reopen)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ITEM_STATUS = SCRIPTS / "item-status.py"


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, str(ITEM_STATUS), *args],
        capture_output=True, text=True, env=env or os.environ.copy(),
    )


def test_show_prints_issue_json(gh_shim, fake_repo):
    r = _run("show", "42")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["number"] == 42


def test_close_with_completed_reason(gh_shim, fake_repo):
    r = _run("close", "42", "--reason", "completed", "--comment", "fixed in #99")
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    assert "issue close" in log
    assert "completed" in log


def test_close_with_not_planned_reason(gh_shim, fake_repo):
    r = _run("close", "42", "--reason", "not-planned")
    assert r.returncode == 0, r.stderr
    assert "not-planned" in gh_shim.read_text()


def test_close_rejects_unknown_reason(gh_shim, fake_repo):
    r = _run("close", "42", "--reason", "wontfix")
    assert r.returncode != 0


def test_reopen(gh_shim, fake_repo):
    r = _run("reopen", "42")
    assert r.returncode == 0, r.stderr
    assert "issue reopen" in gh_shim.read_text()


def test_reopen_with_comment(gh_shim, fake_repo):
    r = _run("reopen", "42", "--comment", "actually still broken")
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    assert "issue reopen" in log
    assert "actually still broken" in log


def test_show_does_not_require_managed(gh_shim, fake_repo, tmp_path, monkeypatch):
    """`show` is read-only; safety guard does not apply."""
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({"number": 7, "labels": [{"name": "bug"}]}))
    env = os.environ.copy()
    env["GH_SHIM_ISSUE_BODY"] = str(body)
    r = _run("show", "7", env=env)
    assert r.returncode == 0, r.stderr
