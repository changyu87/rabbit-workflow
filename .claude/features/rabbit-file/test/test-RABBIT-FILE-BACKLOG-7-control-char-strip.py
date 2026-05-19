#!/usr/bin/env python3
"""
RABBIT-FILE-BACKLOG-7: control-character stripping on title/description.

Both file-item.py and item-status.py update MUST strip ASCII control
characters EXCEPT \\t, \\n, \\r before length validation. The sanitized
value is what gets written to item.json.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FEATURE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = FEATURE_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import branch_ops  # noqa: E402
from conftest import seed_bug_backlog_branch  # noqa: E402


def _git(repo, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args} failed: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture()
def isolated_repo(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                   capture_output=True)
    seed_bug_backlog_branch(remote)  # BUG-32 guard sidestep
    local = tmp_path / "local"
    subprocess.run(["git", "clone", str(remote), str(local)], check=True,
                   capture_output=True)
    _git(local, "config", "user.email", "test@test.invalid")
    _git(local, "config", "user.name", "Test")
    (local / "README").write_text("init")
    _git(local, "add", ".")
    _git(local, "commit", "-m", "init")
    _git(local, "push", "origin", "HEAD:main")

    yield local

    tmp_dir = local / ".claude" / "tmp"
    if tmp_dir.exists():
        for child in tmp_dir.iterdir():
            if child.name.startswith("bug-backlog-files"):
                shutil.rmtree(child, ignore_errors=True)
    subprocess.run(["git", "-C", str(local), "worktree", "prune"],
                   capture_output=True)


@pytest.fixture(autouse=True)
def patch_repo_root(isolated_repo, monkeypatch):
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))


def _run_file_item(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "file-item.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone),
    )


def _run_status(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "item-status.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone),
    )


def _run_list(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "list-items.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone),
    )


def _show_item(clone, feature, type_, id_str):
    r = _run_status(clone, "show", "--feature", feature, "--type", type_,
                    "--id", id_str)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _file_minimal(clone, title="t", description="d", feature="strip"):
    r = _run_file_item(
        clone,
        "--type", "bug", "--feature", feature,
        "--title", title, "--priority", "high",
        "--description", description,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.split()[1]


# ---------------------------------------------------------------------------
# (a) file-item.py strips escape sequences from title
# ---------------------------------------------------------------------------

class TestFileItemTitleStrip:
    def test_escape_sequence_stripped_from_title(self, isolated_repo):
        # \x1b[2J would clear the terminal if echoed by list-items.py.
        dirty = "before\x1b[2Jafter"
        id_str = _file_minimal(isolated_repo, title=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        # ESC stripped; '[2J' is printable and remains.
        assert "\x1b" not in item["title"]
        assert item["title"] == "before[2Jafter"

    def test_bell_and_backspace_stripped(self, isolated_repo):
        # NUL (\x00) cannot be passed via subprocess argv, so we cover the
        # remaining low-ASCII controls here. Bell (\x07) and backspace
        # (\x08) are both <0x20 and not in the {\t,\n,\r} allowlist.
        dirty = "hi\x07\x08!"
        id_str = _file_minimal(isolated_repo, title=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["title"] == "hi!"


# ---------------------------------------------------------------------------
# (b) tab/newline/carriage-return preserved
# ---------------------------------------------------------------------------

class TestWhitespacePreserved:
    def test_tab_newline_cr_preserved_in_title(self, isolated_repo):
        dirty = "a\tb\nc\rd"
        id_str = _file_minimal(isolated_repo, title=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["title"] == "a\tb\nc\rd"

    def test_tab_newline_cr_preserved_in_description(self, isolated_repo):
        dirty = "p\tq\nr\rs"
        id_str = _file_minimal(isolated_repo, description=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["description"] == "p\tq\nr\rs"


# ---------------------------------------------------------------------------
# (c) item-status.py update mirrors stripping behavior
# ---------------------------------------------------------------------------

class TestUpdateMirrorsStrip:
    def test_update_title_strips_escape(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "strip", "--type", "bug", "--id", id_str,
            "--field", "title", "--value", "x\x1b[2Jy",
            "--reason", "strip test",
        )
        assert r.returncode == 0, r.stderr
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert "\x1b" not in item["title"]
        assert item["title"] == "x[2Jy"

    def test_update_description_strips_control_chars(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "strip", "--type", "bug", "--id", id_str,
            # NUL (\x00) cannot ride through subprocess argv; cover the
            # remaining low-ASCII controls (bell \x07, backspace \x08, ESC \x1b).
            "--field", "description", "--value", "foo\x07\x08bar\tbaz\x1b!",
            "--reason", "strip test",
        )
        assert r.returncode == 0, r.stderr
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["description"] == "foobar\tbaz!"

    def test_update_title_preserves_whitespace(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "strip", "--type", "bug", "--id", id_str,
            "--field", "title", "--value", "a\tb\nc\rd",
            "--reason", "ws preserved",
        )
        assert r.returncode == 0, r.stderr
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["title"] == "a\tb\nc\rd"


# ---------------------------------------------------------------------------
# (d) After update, list-items shows sanitized title (no escape bleed)
# ---------------------------------------------------------------------------

class TestListItemsCleanOutput:
    def test_list_items_no_escape_bleed(self, isolated_repo):
        dirty = "evil\x1b[2Jtitle"
        _file_minimal(isolated_repo, title=dirty)
        r = _run_list(isolated_repo, "--type", "bug", "--feature", "strip")
        assert r.returncode == 0, r.stderr
        assert "\x1b" not in r.stdout
        assert "evil[2Jtitle" in r.stdout
