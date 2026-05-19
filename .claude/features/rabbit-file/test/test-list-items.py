#!/usr/bin/env python3
"""Tests for list-items.py"""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"


@pytest.fixture
def isolated_repo(tmp_path, monkeypatch):
    import subprocess as sp
    bare = tmp_path / "remote.git"
    bare.mkdir()
    sp.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    # BUG-32: pre-seed bug-backlog-files so _ensure_branch's local-origin
    # orphan-creation guard does not fire under the bare-local-origin test fixture.
    from conftest import seed_bug_backlog_branch
    seed_bug_backlog_branch(bare)
    clone = tmp_path / "repo"
    sp.run(["git", "clone", str(bare), str(clone)], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "config", "user.name", "Tester"], check=True, capture_output=True)
    branch = sp.run(["git", "-C", str(clone), "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True).stdout.strip() or "main"
    (clone / "README").write_text("init")
    sp.run(["git", "-C", str(clone), "add", "."], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "commit", "-m", "init"], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "push", "origin", branch], check=True, capture_output=True)

    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))
    return clone


@pytest.fixture
def populated_repo(isolated_repo, monkeypatch):
    """Repo with 3 items: 2 bugs (one open, one closed) and 1 backlog (open)."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))

    base = {"title": "T", "description": "D", "related_feature": "feat-a",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "tester", "closed": None,
            "history": []}

    id1 = branch_ops.allocate_id("feat-a", "bug")
    branch_ops.commit_item("feat-a", "bug", id1,
        {**base, "name": id1, "type": "bug", "status": "open", "priority": "high", "title": "Open bug"})

    id2 = branch_ops.allocate_id("feat-a", "bug")
    branch_ops.commit_item("feat-a", "bug", id2,
        {**base, "name": id2, "type": "bug", "status": "close", "priority": "low",
         "title": "Closed bug", "closed": "2026-01-02T00:00:00Z"})

    id3 = branch_ops.allocate_id("feat-a", "backlog")
    branch_ops.commit_item("feat-a", "backlog", id3,
        {**base, "name": id3, "type": "backlog", "status": "open", "priority": "medium",
         "title": "Open backlog"})

    return isolated_repo, id1, id2, id3


def run_list(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "list-items.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone)
    )


def test_no_branch_prints_guidance(isolated_repo):
    # The fixture pre-seeds bug-backlog-files (BUG-32 guard sidestep).
    # Delete it on the bare remote so list-items.py sees "no branch".
    import subprocess as sp
    bare = isolated_repo.parent / "remote.git"
    sp.run(["git", "-C", str(bare), "branch", "-D", "bug-backlog-files"],
           check=True, capture_output=True)
    r = run_list(isolated_repo)
    assert r.returncode == 0
    assert "No items filed yet" in r.stdout


def test_type_bug_returns_only_bugs(populated_repo):
    clone, id1, id2, id3 = populated_repo
    r = run_list(clone, "--type", "bug")
    assert r.returncode == 0
    assert id1 in r.stdout
    assert id2 in r.stdout
    assert id3 not in r.stdout


def test_type_all_returns_all(populated_repo):
    clone, id1, id2, id3 = populated_repo
    r = run_list(clone)
    assert r.returncode == 0
    assert id1 in r.stdout
    assert id2 in r.stdout
    assert id3 in r.stdout


def test_status_open_filters(populated_repo):
    clone, id1, id2, id3 = populated_repo
    r = run_list(clone, "--status", "open")
    assert r.returncode == 0
    assert id1 in r.stdout
    assert id2 not in r.stdout
    assert id3 in r.stdout


def test_feature_filter(populated_repo):
    clone, id1, id2, id3 = populated_repo
    r = run_list(clone, "--feature", "feat-a")
    assert r.returncode == 0
    assert id1 in r.stdout
    assert id2 in r.stdout
    assert id3 in r.stdout


def test_output_format(populated_repo):
    clone, id1, id2, id3 = populated_repo
    r = run_list(clone, "--type", "bug", "--status", "open")
    assert r.returncode == 0
    # Format: NAME  [TYPE]  [STATUS]  [PRIORITY]  TITLE
    line = [l for l in r.stdout.strip().splitlines() if id1 in l][0]
    assert "[bug]" in line
    assert "[open]" in line
    assert "[high]" in line
    assert "Open bug" in line


def test_no_items_found_with_filter(populated_repo):
    clone, *_ = populated_repo
    r = run_list(clone, "--feature", "nonexistent-feature")
    assert r.returncode == 0
    assert "No items found." in r.stdout
