#!/usr/bin/env python3
"""
Sanitize and length invariants for title/description fields.

Two spec invariants are exercised here:

  1. Per-field length limits — enforced symmetrically by BOTH file-item.py
     (filing time) and item-status.py update (mutation time):
        MAX_TITLE_LEN       = 200
        MAX_DESCRIPTION_LEN = 10240

  2. Control-character stripping — file-item.py and item-status.py update
     MUST strip ASCII control characters EXCEPT \\t, \\n, \\r before
     length validation. The sanitized value is what gets written to
     item.json (protects list-items.py output from terminal escape
     injection).
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


def _file_minimal(clone, title="t", description="d", feature="lf"):
    r = _run_file_item(
        clone,
        "--type", "bug", "--feature", feature,
        "--title", title, "--priority", "high",
        "--description", description,
    )
    assert r.returncode == 0, r.stderr
    # Filed: <ID>  sha: <sha>
    id_str = r.stdout.split()[1]
    return id_str


# ---------------------------------------------------------------------------
# (a) file-item.py title length boundary
# ---------------------------------------------------------------------------

class TestFileItemTitleLength:
    def test_title_at_200_accepted(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "x" * 200, "--priority", "high",
            "--description", "d",
        )
        assert r.returncode == 0, r.stderr

    def test_title_201_rejected(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "x" * 201, "--priority", "high",
            "--description", "d",
        )
        assert r.returncode != 0
        assert "title" in r.stderr
        assert "200" in r.stderr


# ---------------------------------------------------------------------------
# (b) file-item.py description length boundary
# ---------------------------------------------------------------------------

class TestFileItemDescriptionLength:
    def test_description_at_10240_accepted(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", "y" * 10240,
        )
        assert r.returncode == 0, r.stderr

    def test_description_10241_rejected(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", "y" * 10241,
        )
        assert r.returncode != 0
        assert "description" in r.stderr
        assert "10240" in r.stderr


# ---------------------------------------------------------------------------
# (c) item-status.py update --field title boundary
# ---------------------------------------------------------------------------

class TestUpdateTitleLength:
    def test_title_at_200_accepted(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "title", "--value", "x" * 200,
            "--reason", "boundary",
        )
        assert r.returncode == 0, r.stderr

    def test_title_201_rejected(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "title", "--value", "x" * 201,
            "--reason", "boundary",
        )
        assert r.returncode != 0
        assert "title" in r.stderr
        assert "200" in r.stderr


# ---------------------------------------------------------------------------
# (d) item-status.py update --field description boundary
# ---------------------------------------------------------------------------

class TestUpdateDescriptionLength:
    def test_description_at_10240_accepted(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", "y" * 10240,
            "--reason", "boundary",
        )
        assert r.returncode == 0, r.stderr

    def test_description_10241_rejected(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", "y" * 10241,
            "--reason", "boundary",
        )
        assert r.returncode != 0
        assert "description" in r.stderr
        assert "10240" in r.stderr


# ---------------------------------------------------------------------------
# (e) Symmetry: oversized description rejected by BOTH scripts consistently
# ---------------------------------------------------------------------------

class TestSymmetry:
    def test_file_item_and_update_reject_oversize_description(self, isolated_repo):
        oversize = "z" * 10241

        # file-item.py rejects.
        r_file = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", oversize,
        )
        assert r_file.returncode != 0
        assert "description" in r_file.stderr
        assert "10240" in r_file.stderr

        # update rejects too.
        id_str = _file_minimal(isolated_repo)
        r_upd = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", oversize,
            "--reason", "test",
        )
        assert r_upd.returncode != 0
        assert "description" in r_upd.stderr
        assert "10240" in r_upd.stderr


# ---------------------------------------------------------------------------
# (f) Old 500-char limit is gone: 501-char description now succeeds
# ---------------------------------------------------------------------------

class TestOldLimitRemoved:
    def test_update_501_char_description_succeeds(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", "d" * 501,
            "--reason", "old limit gone",
        )
        assert r.returncode == 0, r.stderr

    def test_file_item_501_char_description_succeeds(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", "d" * 501,
        )
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# Control-character sanitisation
# ---------------------------------------------------------------------------


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


def _file_minimal_strip(clone, title="t", description="d", feature="strip"):
    r = _run_file_item(
        clone,
        "--type", "bug", "--feature", feature,
        "--title", title, "--priority", "high",
        "--description", description,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.split()[1]


class TestFileItemTitleStrip:
    def test_escape_sequence_stripped_from_title(self, isolated_repo):
        # \x1b[2J would clear the terminal if echoed by list-items.py.
        dirty = "before\x1b[2Jafter"
        id_str = _file_minimal_strip(isolated_repo, title=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        # ESC stripped; '[2J' is printable and remains.
        assert "\x1b" not in item["title"]
        assert item["title"] == "before[2Jafter"

    def test_bell_and_backspace_stripped(self, isolated_repo):
        # NUL (\x00) cannot be passed via subprocess argv, so we cover the
        # remaining low-ASCII controls here. Bell (\x07) and backspace
        # (\x08) are both <0x20 and not in the {\t,\n,\r} allowlist.
        dirty = "hi\x07\x08!"
        id_str = _file_minimal_strip(isolated_repo, title=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["title"] == "hi!"


class TestWhitespacePreserved:
    def test_tab_newline_cr_preserved_in_title(self, isolated_repo):
        dirty = "a\tb\nc\rd"
        id_str = _file_minimal_strip(isolated_repo, title=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["title"] == "a\tb\nc\rd"

    def test_tab_newline_cr_preserved_in_description(self, isolated_repo):
        dirty = "p\tq\nr\rs"
        id_str = _file_minimal_strip(isolated_repo, description=dirty)
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["description"] == "p\tq\nr\rs"


class TestUpdateMirrorsStrip:
    def test_update_title_strips_escape(self, isolated_repo):
        id_str = _file_minimal_strip(isolated_repo)
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
        id_str = _file_minimal_strip(isolated_repo)
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
        id_str = _file_minimal_strip(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "strip", "--type", "bug", "--id", id_str,
            "--field", "title", "--value", "a\tb\nc\rd",
            "--reason", "ws preserved",
        )
        assert r.returncode == 0, r.stderr
        item = _show_item(isolated_repo, "strip", "bug", id_str)
        assert item["title"] == "a\tb\nc\rd"


class TestListItemsCleanOutput:
    def test_list_items_no_escape_bleed(self, isolated_repo):
        dirty = "evil\x1b[2Jtitle"
        _file_minimal_strip(isolated_repo, title=dirty)
        r = _run_list(isolated_repo, "--type", "bug", "--feature", "strip")
        assert r.returncode == 0, r.stderr
        assert "\x1b" not in r.stdout
        assert "evil[2Jtitle" in r.stdout


# ---------------------------------------------------------------------------
# Unit tests: sanitize_text behaviour (independent of git/I-O)
# ---------------------------------------------------------------------------


class TestSanitizeText:
    def test_empty_string(self):
        assert branch_ops.sanitize_text("") == ""

    def test_plain_ascii_unchanged(self):
        assert branch_ops.sanitize_text("hello world") == "hello world"

    def test_allowed_whitespace_preserved(self):
        assert branch_ops.sanitize_text("a\tb\nc\rd") == "a\tb\nc\rd"

    def test_all_control_chars_stripped(self):
        forbidden = "".join(
            chr(i) for i in range(0x20)
            if chr(i) not in ("\t", "\n", "\r")
        )
        assert branch_ops.sanitize_text(forbidden) == ""

    def test_esc_stripped_protects_against_terminal_injection(self):
        evil = "title\x1b[2J\x1b[H"
        assert branch_ops.sanitize_text(evil) == "title[2J[H"

    def test_mixed_content(self):
        assert (
            branch_ops.sanitize_text("good\x00\tbetter\x07\nbest")
            == "good\tbetter\nbest"
        )

    def test_multi_byte_unicode_preserved(self):
        text = "rabbit cafe naive eu \U0001f407"
        assert branch_ops.sanitize_text(text) == text


# ---------------------------------------------------------------------------
# Unit tests: validate_field_length boundary behaviour
# ---------------------------------------------------------------------------


class TestValidateFieldLength:
    def test_under_limit_passes(self):
        branch_ops.validate_field_length("title", "abc", limit=10)

    def test_at_limit_passes(self):
        branch_ops.validate_field_length("title", "x" * 10, limit=10)

    def test_one_over_limit_raises(self):
        with pytest.raises(ValueError) as exc_info:
            branch_ops.validate_field_length("title", "x" * 11, limit=10)
        msg = str(exc_info.value)
        assert "title" in msg
        assert "10" in msg
        assert "11" in msg

    def test_description_far_over_limit_raises(self):
        big = "z" * (branch_ops.MAX_DESCRIPTION_LEN + 1)
        with pytest.raises(ValueError) as exc_info:
            branch_ops.validate_field_length(
                "description", big, limit=branch_ops.MAX_DESCRIPTION_LEN
            )
        assert "description" in str(exc_info.value)
