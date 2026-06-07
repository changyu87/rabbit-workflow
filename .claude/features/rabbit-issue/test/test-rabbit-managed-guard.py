"""Regression test for the actionability safety invariant.

`item-status.py close` and `item-status.py reopen` MUST refuse to act on
issues that are NOT actionable — i.e. that lack a valid `feature:` label.
A raw, hand-filed GitHub issue with no labels stays out of rabbit's
automation reach. An actionable issue (carrying a `feature:` label) is
permitted.

Rebased from the legacy `rabbit-managed`-label basis to the actionability
basis in coexistence step 2 of #753 (#759).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ITEM_STATUS = SCRIPTS / "item-status.py"


def _env_with_issue(tmp_path, labels):
    body = tmp_path / "issue.json"
    body.write_text(json.dumps({
        "number": 5,
        "labels": [{"name": n} for n in labels],
    }))
    env = os.environ.copy()
    env["GH_SHIM_ISSUE_BODY"] = str(body)
    return env


def _non_actionable_env(tmp_path):
    # No feature: label -> not actionable. (rabbit-managed alone is NOT
    # enough under the actionability basis.)
    return _env_with_issue(tmp_path, ["bug", "rabbit-managed"])


def _actionable_env(tmp_path):
    # Carries a valid feature: label -> actionable.
    return _env_with_issue(tmp_path, ["bug", "feature:rabbit-cage", "priority:high"])


def test_close_refused_when_not_actionable(gh_shim, fake_repo, tmp_path):
    env = _non_actionable_env(tmp_path)
    r = subprocess.run(
        [sys.executable, str(ITEM_STATUS), "close", "5", "--reason", "completed"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode != 0
    assert "actionable" in (r.stderr + r.stdout).lower()
    # no `issue close` ever issued
    assert "issue close" not in gh_shim.read_text()


def test_reopen_refused_when_not_actionable(gh_shim, fake_repo, tmp_path):
    env = _non_actionable_env(tmp_path)
    r = subprocess.run(
        [sys.executable, str(ITEM_STATUS), "reopen", "5"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode != 0
    assert "actionable" in (r.stderr + r.stdout).lower()
    assert "issue reopen" not in gh_shim.read_text()


def test_close_refused_when_no_labels_at_all(gh_shim, fake_repo, tmp_path):
    """A raw hand-filed issue with no labels is not auto-mutated."""
    env = _env_with_issue(tmp_path, [])
    r = subprocess.run(
        [sys.executable, str(ITEM_STATUS), "reopen", "5"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode != 0
    assert "issue reopen" not in gh_shim.read_text()


def test_reopen_permitted_when_actionable(gh_shim, fake_repo, tmp_path):
    env = _actionable_env(tmp_path)
    r = subprocess.run(
        [sys.executable, str(ITEM_STATUS), "reopen", "5"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "issue reopen" in gh_shim.read_text()
