"""Regression test for the rabbit-managed safety invariant.

`item-status.py close` and `item-status.py reopen` MUST refuse to act on
issues lacking the `rabbit-managed` label. Human-filed issues stay out of
rabbit's automation reach.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ITEM_STATUS = SCRIPTS / "item-status.py"


def _unmanaged_env(tmp_path):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({"number": 5, "labels": [{"name": "bug"}]}))
    env = os.environ.copy()
    env["GH_SHIM_ISSUE_BODY"] = str(body)
    return env


def test_close_refused_when_no_rabbit_managed_label(gh_shim, fake_repo, tmp_path):
    env = _unmanaged_env(tmp_path)
    r = subprocess.run(
        [sys.executable, str(ITEM_STATUS), "close", "5", "--reason", "completed"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode != 0
    assert "rabbit-managed" in (r.stderr + r.stdout)
    # no `issue close` ever issued
    assert "issue close" not in gh_shim.read_text()


def test_reopen_refused_when_no_rabbit_managed_label(gh_shim, fake_repo, tmp_path):
    env = _unmanaged_env(tmp_path)
    r = subprocess.run(
        [sys.executable, str(ITEM_STATUS), "reopen", "5"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode != 0
    assert "rabbit-managed" in (r.stderr + r.stdout)
    assert "issue reopen" not in gh_shim.read_text()
