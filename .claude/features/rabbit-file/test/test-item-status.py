#!/usr/bin/env python3
"""Tests for item-status.py"""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
TEST_DIR = Path(__file__).parent


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
def filed_item(isolated_repo, monkeypatch):
    """File a bug item and return (clone, id_str)."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))

    id_str = branch_ops.allocate_id("test-feat", "bug")
    item = {
        "name": id_str, "type": "bug", "title": "Test", "status": "open",
        "priority": "high", "description": "desc", "related_feature": "test-feat",
        "filed": "2026-01-01T00:00:00Z", "filed_by": "tester", "closed": None,
        "history": [{"ts": "2026-01-01T00:00:00Z", "actor": "tester", "action": "opened", "note": "initial filing"}],
    }
    branch_ops.commit_item("test-feat", "bug", id_str, item)
    return isolated_repo, id_str


def run_cmd(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "item-status.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone)
    )


def test_get_returns_status(filed_item):
    clone, id_str = filed_item
    r = run_cmd(clone, "get", "--feature", "test-feat", "--type", "bug", "--id", id_str)
    assert r.returncode == 0
    assert r.stdout.strip() == "open"


def test_get_missing_item_exits_1(isolated_repo):
    r = run_cmd(isolated_repo, "get", "--feature", "test-feat", "--type", "bug", "--id", "MISSING-1")
    assert r.returncode == 1


def test_set_missing_reason_exits_1(filed_item):
    clone, id_str = filed_item
    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "close")
    assert r.returncode != 0


def test_set_open_to_close(filed_item, monkeypatch):
    clone, id_str = filed_item
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))

    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "close", "--reason", "fixed it")
    assert r.returncode == 0, r.stderr
    assert f"Status set: {id_str} -> close" in r.stdout

    item = branch_ops.fetch_item("test-feat", "bug", id_str)
    assert item["status"] == "close"
    assert item["closed"] is not None
    assert item["history"][-1]["action"] == "closed"
    assert item["history"][-1]["note"] == "fixed it"


def test_set_close_to_open(filed_item, monkeypatch):
    clone, id_str = filed_item
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))

    # First close it
    run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
            "--id", id_str, "--status", "close", "--reason", "done")
    # Then reopen
    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "open", "--reason", "actually not done")
    assert r.returncode == 0, r.stderr

    item = branch_ops.fetch_item("test-feat", "bug", id_str)
    assert item["status"] == "open"
    assert item["closed"] is None
    assert item["history"][-1]["action"] == "opened"


def test_set_with_fix_commits(filed_item, monkeypatch):
    clone, id_str = filed_item
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))

    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "close", "--reason", "fixed",
                "--fix-commits", "abc123def456")
    assert r.returncode == 0, r.stderr

    item = branch_ops.fetch_item("test-feat", "bug", id_str)
    assert item["history"][-1]["fix_commits"] == "abc123def456"


# --- update subcommand tests ---


def _fetch(clone, monkeypatch, id_str, type_="bug", feature="test-feat"):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))
    return branch_ops.fetch_item(feature, type_, id_str)


def test_update_priority_happy_path(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "priority", "--value", "low",
                "--reason", "lower than thought")
    assert r.returncode == 0, r.stderr

    item = _fetch(clone, monkeypatch, id_str)
    assert item["priority"] == "low"
    h = item["history"][-1]
    assert h["action"] == "updated"
    assert h["field"] == "priority"
    assert h["old_value"] == "high"
    assert h["new_value"] == "low"
    assert h["note"] == "lower than thought"
    assert "ts" in h and h["ts"]
    assert "actor" in h and h["actor"]


def test_update_title_happy_path(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "title", "--value", "New Title",
                "--reason", "clarify")
    assert r.returncode == 0, r.stderr

    item = _fetch(clone, monkeypatch, id_str)
    assert item["title"] == "New Title"
    h = item["history"][-1]
    assert h["action"] == "updated"
    assert h["field"] == "title"
    assert h["old_value"] == "Test"
    assert h["new_value"] == "New Title"
    assert h["note"] == "clarify"


def test_update_description_happy_path(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "description", "--value", "more detail",
                "--reason", "expand")
    assert r.returncode == 0, r.stderr

    item = _fetch(clone, monkeypatch, id_str)
    assert item["description"] == "more detail"
    h = item["history"][-1]
    assert h["action"] == "updated"
    assert h["field"] == "description"
    assert h["old_value"] == "desc"
    assert h["new_value"] == "more detail"


def test_update_rejects_closed_item(filed_item, monkeypatch):
    clone, id_str = filed_item
    # close it first
    run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
            "--id", id_str, "--status", "close", "--reason", "done")
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "priority", "--value", "low",
                "--reason", "try update")
    assert r.returncode == 1
    assert "reopen" in r.stderr.lower()

    item = _fetch(clone, monkeypatch, id_str)
    assert item["priority"] == "high"
    # no 'updated' history entry was appended
    assert all(h.get("action") != "updated" for h in item["history"])


def test_update_rejects_unknown_field(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "nonsense", "--value", "x",
                "--reason", "try")
    assert r.returncode == 1
    # error message lists allowed fields
    assert "priority" in r.stderr
    assert "title" in r.stderr
    assert "description" in r.stderr


def test_update_rejects_immutable_status_field(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "status", "--value", "close",
                "--reason", "try")
    assert r.returncode == 1


def test_update_rejects_immutable_history_field(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "history", "--value", "[]",
                "--reason", "try")
    assert r.returncode == 1


def test_update_rejects_immutable_commit_sha_field(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "commit_sha", "--value", "abc",
                "--reason", "try")
    assert r.returncode == 1


def test_update_rejects_invalid_priority_value(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "priority", "--value", "medium-high",
                "--reason", "try")
    assert r.returncode == 1
    # error message names the valid set
    for p in ("low", "medium", "high", "critical"):
        assert p in r.stderr


def test_update_rejects_empty_reason(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "priority", "--value", "low",
                "--reason", "   ")
    assert r.returncode == 1


def test_update_rejects_empty_value(filed_item, monkeypatch):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "title", "--value", "",
                "--reason", "try")
    assert r.returncode == 1


def test_update_noop_when_value_unchanged(filed_item, monkeypatch):
    clone, id_str = filed_item
    item_before = _fetch(clone, monkeypatch, id_str)
    history_len_before = len(item_before["history"])

    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "priority", "--value", "high",
                "--reason", "no change attempt")
    assert r.returncode == 0, r.stderr

    item_after = _fetch(clone, monkeypatch, id_str)
    assert item_after["priority"] == "high"
    # no history entry appended
    assert len(item_after["history"]) == history_len_before


def test_update_missing_field_arg_argparse_exit(filed_item):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--value", "low", "--reason", "x")
    assert r.returncode == 2


def test_update_missing_value_arg_argparse_exit(filed_item):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "priority", "--reason", "x")
    assert r.returncode == 2


def test_update_missing_reason_arg_argparse_exit(filed_item):
    clone, id_str = filed_item
    r = run_cmd(clone, "update", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--field", "priority", "--value", "low")
    assert r.returncode == 2


# --- BUG-11: set must short-circuit no-op transitions ---


def test_set_open_to_open_is_noop(filed_item, monkeypatch):
    """A `set --status open` on an already-open item must exit 0, print a
    no-op message naming the current status, append NO history entry, and
    create NO commit on bug-backlog-files."""
    clone, id_str = filed_item

    item_before = _fetch(clone, monkeypatch, id_str)
    assert item_before["status"] == "open"
    history_len_before = len(item_before["history"])

    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "open", "--reason", "redundant open")
    assert r.returncode == 0, r.stderr
    # stdout names the no-op and the current status
    assert "no-op" in r.stdout.lower(), (
        f"expected stdout to contain 'no-op', got: {r.stdout!r}"
    )
    assert "open" in r.stdout, (
        f"expected stdout to name current status 'open', got: {r.stdout!r}"
    )

    item_after = _fetch(clone, monkeypatch, id_str)
    # No history entry was appended
    assert len(item_after["history"]) == history_len_before, (
        f"history grew on no-op transition: before={history_len_before} "
        f"after={len(item_after['history'])}"
    )
    # Status unchanged, closed timestamp unchanged
    assert item_after["status"] == "open"
    assert item_after["closed"] is None


def test_set_close_to_close_is_noop(filed_item, monkeypatch):
    """A `set --status close` on an already-closed item must exit 0, print a
    no-op message, append NO history entry, and NOT mutate the closed timestamp."""
    clone, id_str = filed_item

    # First close it (real transition).
    r1 = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                 "--id", id_str, "--status", "close", "--reason", "fixed")
    assert r1.returncode == 0, r1.stderr

    item_after_close = _fetch(clone, monkeypatch, id_str)
    assert item_after_close["status"] == "close"
    closed_ts_before = item_after_close["closed"]
    history_len_before = len(item_after_close["history"])

    # Re-close: must be a no-op.
    r2 = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                 "--id", id_str, "--status", "close", "--reason", "redundant close")
    assert r2.returncode == 0, r2.stderr
    assert "no-op" in r2.stdout.lower(), (
        f"expected stdout to contain 'no-op', got: {r2.stdout!r}"
    )
    assert "close" in r2.stdout, (
        f"expected stdout to name current status 'close', got: {r2.stdout!r}"
    )

    item_after = _fetch(clone, monkeypatch, id_str)
    assert len(item_after["history"]) == history_len_before, (
        "history grew on redundant close"
    )
    assert item_after["status"] == "close"
    # The closed timestamp must not be rewritten by a no-op.
    assert item_after["closed"] == closed_ts_before, (
        f"closed timestamp changed on no-op: before={closed_ts_before!r} "
        f"after={item_after['closed']!r}"
    )
