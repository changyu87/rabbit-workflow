"""E2E tests for scripts/item-status.py (show / close / reopen).

Close-path gating (issue #423):
  - `--reason completed`  requires `--commit-sha <sha>`; the sha must
    resolve to a real commit in the local git repo.
  - `--reason not-planned` requires `--reason-text <text>` of >= 50 chars
    that is free of banned boilerplate phrases.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ITEM_STATUS = SCRIPTS / "item-status.py"

# A specific, non-boilerplate, >= 50-char reason for not-planned closes.
GOOD_REASON = (
    "Superseded by the new sandbox executor introduced in PR #410; "
    "the code path this issue targets no longer exists after that refactor."
)


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, str(ITEM_STATUS), *args],
        capture_output=True, text=True, env=env or os.environ.copy(),
    )


def _commit_in(repo):
    """Create one commit in `repo` and return its full SHA."""
    subprocess.run(["git", "-C", str(repo), "config", "user.email",
                    "t@t.t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name",
                    "t"], check=True)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"],
                   check=True)
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()


def test_show_prints_issue_json(gh_shim, fake_repo):
    r = _run("show", "42")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["number"] == 42


def test_close_completed_requires_commit_sha(gh_shim, fake_repo):
    """`--reason completed` without `--commit-sha` is rejected."""
    r = _run("close", "42", "--reason", "completed", "--comment", "done")
    assert r.returncode != 0
    log = gh_shim.read_text()
    assert "issue close" not in log


def test_close_completed_with_valid_sha(gh_shim, fake_repo):
    sha = _commit_in(fake_repo)
    r = _run("close", "42", "--reason", "completed", "--commit-sha", sha,
             "--comment", "fixed")
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    assert "issue close" in log
    assert "completed" in log


def test_close_completed_with_invalid_sha(gh_shim, fake_repo):
    _commit_in(fake_repo)
    r = _run("close", "42", "--reason", "completed",
             "--commit-sha", "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    assert r.returncode != 0
    assert "issue close" not in gh_shim.read_text()


def test_close_not_planned_requires_reason_text(gh_shim, fake_repo):
    """`--reason not-planned` without `--reason-text` is rejected."""
    r = _run("close", "42", "--reason", "not-planned")
    assert r.returncode != 0
    assert "issue close" not in gh_shim.read_text()


def test_close_not_planned_rejects_short_reason(gh_shim, fake_repo):
    r = _run("close", "42", "--reason", "not-planned",
             "--reason-text", "stale")
    assert r.returncode != 0
    assert "issue close" not in gh_shim.read_text()


def test_close_not_planned_rejects_boilerplate(gh_shim, fake_repo):
    """A 50+ char reason that contains a banned phrase is still rejected."""
    boiler = ("This one is honestly too risky to attempt right now so we "
              "are going to leave it for some later time, thanks.")
    assert len(boiler) >= 50
    r = _run("close", "42", "--reason", "not-planned",
             "--reason-text", boiler)
    assert r.returncode != 0
    assert "issue close" not in gh_shim.read_text()


def test_close_not_planned_accepts_specific_reason(gh_shim, fake_repo):
    assert len(GOOD_REASON) >= 50
    r = _run("close", "42", "--reason", "not-planned",
             "--reason-text", GOOD_REASON)
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    # #419 translation kept intact: hyphenated form becomes the space form
    # gh expects, and the hyphen form never reaches gh.
    assert "issue close" in log
    assert "not planned" in log
    assert "not-planned" not in log


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
