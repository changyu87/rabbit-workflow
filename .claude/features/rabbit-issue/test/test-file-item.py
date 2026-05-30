"""E2E tests for scripts/file-item.py.

Driven via subprocess so PATH-shimmed `gh` is the same one the script sees.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FILE_ITEM = SCRIPTS / "file-item.py"


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, str(FILE_ITEM), *args],
        capture_output=True, text=True, env=env or os.environ.copy(),
    )


def test_file_bug_creates_gh_issue(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "rabbit-cage",
        "--title", "login button broken on Safari",
        "--priority", "high",
        "--description", "steps: ...",
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["number"] == 9001
    assert out["type"] == "bug"
    assert out["url"] == "https://github.com/test/repo/issues/9001"
    log = gh_shim.read_text()
    assert "issue create" in log
    for lbl in ("bug", "rabbit-managed", "feature:rabbit-cage", "priority:high"):
        assert lbl in log


def test_file_enhancement_uses_enhancement_label(gh_shim, fake_repo):
    r = _run(
        "--type", "enhancement",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    assert "enhancement" in gh_shim.read_text()


def test_rejects_invalid_type(gh_shim, fake_repo):
    r = _run(
        "--type", "feature",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
    )
    assert r.returncode != 0
    assert "type" in r.stderr.lower() or "invalid" in r.stderr.lower()


def test_rejects_invalid_priority(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "x",
        "--title", "t",
        "--priority", "urgent",
        "--description", "d",
    )
    assert r.returncode != 0


def test_ensure_labels_called_before_create(gh_shim, fake_repo):
    r = _run(
        "--type", "bug",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
    )
    assert r.returncode == 0, r.stderr
    log_lines = gh_shim.read_text().strip().split("\n")
    label_idx = next(i for i, l in enumerate(log_lines) if l.startswith("label create"))
    issue_idx = next(i for i, l in enumerate(log_lines) if l.startswith("issue create"))
    assert label_idx < issue_idx


def test_requires_auth(gh_shim, fake_repo, monkeypatch):
    env = os.environ.copy()
    env["GH_SHIM_AUTH_EXIT"] = "1"
    r = _run(
        "--type", "bug",
        "--feature", "x",
        "--title", "t",
        "--priority", "low",
        "--description", "d",
        env=env,
    )
    assert r.returncode != 0
    # auth failure must short-circuit before any issue create
    assert "issue create" not in gh_shim.read_text()
