#!/usr/bin/env python3
"""
Tests for rabbit-file bug fixes and backlog items:
  BUG-10  — id-slot rollback on commit_item failure
  BUG-21  — canonical ID format with hyphenated feature names
  BUG-24  — read_branch logs malformed items to stderr
  BUG-28  — list-items.py distinguishes 'no branch' from 'no items found'
  BUG-30  — list-items.py output is deterministic (sorted by name)
  BACKLOG-3  — explicit concurrent allocate_id race test
  BACKLOG-4  — caller-dict-not-mutated, init-failure-cleanup, corrupted-JSON skip
  BACKLOG-7  — item-status update length validation
  BACKLOG-8  — item-status show subcommand
  BACKLOG-10 — module-level constants for branch name and identity
"""
import json
import os
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


# ---------------------------------------------------------------------------
# BUG-21: canonical ID format
# ---------------------------------------------------------------------------

class TestCanonicalIdFormat:
    def test_hyphenated_feature_name_preserves_hyphens(self):
        assert branch_ops._format_id("rabbit-cage", "bug", 17) == "RABBIT-CAGE-BUG-17"

    def test_multi_hyphen_feature_name(self):
        assert branch_ops._format_id("my-feature-x", "backlog", 3) == "MY-FEATURE-X-BACKLOG-3"

    def test_unhyphenated_feature_name(self):
        assert branch_ops._format_id("single", "bug", 1) == "SINGLE-BUG-1"

    def test_id_format_documented_in_spec(self):
        spec = (FEATURE_DIR / "docs" / "spec" / "spec.md").read_text()
        assert "UPPER(feature)-UPPER(type)-N" in spec, (
            "spec must document canonical ID format"
        )


# ---------------------------------------------------------------------------
# BACKLOG-10: module-level constants
# ---------------------------------------------------------------------------

class TestModuleConstants:
    def test_branch_constant_exposed(self):
        assert hasattr(branch_ops, "BRANCH")
        assert branch_ops.BRANCH == "bug-backlog-files"

    def test_identity_constants_exposed(self):
        assert hasattr(branch_ops, "IDENTITY_NAME")
        assert hasattr(branch_ops, "IDENTITY_EMAIL")
        assert branch_ops.IDENTITY_NAME == "rabbit-file"
        assert branch_ops.IDENTITY_EMAIL == "rabbit-file@localhost"


# ---------------------------------------------------------------------------
# BUG-10: ID slot rollback on commit_item failure
# ---------------------------------------------------------------------------

class TestIdRollbackOnCommitFailure:
    def test_release_id_decrements_counter_when_safe(self, isolated_repo):
        """After allocate_id reserves ID N+1, release_id rolls back when no
        other process has allocated above it."""
        id_str = branch_ops.allocate_id("rollback-feat", "bug")
        # ID was 1; counter.next is now 2.
        # Call release_id — counter should go back to 1.
        branch_ops.release_id("rollback-feat", "bug", id_str)
        # Next allocate should reuse ID 1.
        next_id = branch_ops.allocate_id("rollback-feat", "bug")
        assert next_id == "ROLLBACK-FEAT-BUG-1", (
            f"after release_id, next allocate should reuse ID 1, got {next_id}"
        )

    def test_release_id_noop_when_slot_consumed_above(self, isolated_repo):
        """If another allocation happened after our reservation, release_id
        is a no-op (best-effort): the counter is NOT moved."""
        id1 = branch_ops.allocate_id("noop-feat", "bug")  # ID 1, counter=2
        id2 = branch_ops.allocate_id("noop-feat", "bug")  # ID 2, counter=3
        # Try to release id1 — but counter is at 3, not 2, so it's unsafe.
        branch_ops.release_id("noop-feat", "bug", id1)
        # Next allocation should be ID 3 (unchanged).
        id3 = branch_ops.allocate_id("noop-feat", "bug")
        assert id3 == "NOOP-FEAT-BUG-3", (
            f"release_id must not move counter when slot was consumed above, got {id3}"
        )

    def test_file_item_rolls_back_id_on_commit_failure(self, isolated_repo,
                                                       monkeypatch):
        """When commit_item raises after allocate_id succeeded, file-item.py
        invokes release_id so the ID slot is reclaimed for the next caller."""
        # Patch branch_ops.commit_item (loaded inside the file-item.py
        # subprocess) by patching via PYTHONPATH and a wrapper module.
        # We do this by running file-item.py with an env that forces
        # commit_item failure via a sitecustomize-style override.
        sitepath = isolated_repo / "_pytest_inject"
        sitepath.mkdir()
        (sitepath / "sitecustomize.py").write_text(
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, {str(SCRIPTS_DIR)!r})\n"
            "import branch_ops as _bo\n"
            "_orig = _bo.commit_item\n"
            "def _boom(*a, **kw):\n"
            "    raise RuntimeError('simulated commit_item failure')\n"
            "_bo.commit_item = _boom\n"
        )

        env = os.environ.copy()
        env["PYTHONPATH"] = (
            str(sitepath) + os.pathsep + env.get("PYTHONPATH", "")
        )

        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "file-item.py"),
             "--type", "bug", "--feature", "rollback-e2e",
             "--title", "T", "--priority", "high",
             "--description", "D", "--filed-by", "tester"],
            capture_output=True, text=True, cwd=str(isolated_repo), env=env,
        )
        assert r.returncode != 0, (
            f"file-item.py should fail when commit_item raises; "
            f"stdout={r.stdout!r} stderr={r.stderr!r}"
        )

        # Now a SECOND filing (without the injected failure) MUST reuse ID 1
        # because the rollback released the slot.
        r2 = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "file-item.py"),
             "--type", "bug", "--feature", "rollback-e2e",
             "--title", "T2", "--priority", "high",
             "--description", "D2", "--filed-by", "tester"],
            capture_output=True, text=True, cwd=str(isolated_repo),
        )
        assert r2.returncode == 0, r2.stderr
        assert "ROLLBACK-E2E-BUG-1" in r2.stdout, (
            f"after rollback, next filing should reuse ID 1; got: {r2.stdout!r}"
        )


# ---------------------------------------------------------------------------
# BUG-24: read_branch logs malformed JSON to stderr
# ---------------------------------------------------------------------------

class TestMalformedJsonLogging:
    def test_read_branch_logs_malformed_item_to_stderr(self, isolated_repo,
                                                       capsys):
        # File a valid item.
        id_str = branch_ops.allocate_id("malformed-feat", "bug")
        item = {
            "name": id_str, "type": "bug", "title": "Valid",
            "status": "open", "priority": "low", "description": "x",
            "related_feature": "malformed-feat",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "tester",
            "closed": None, "history": [],
        }
        branch_ops.commit_item("malformed-feat", "bug", id_str, item)

        # Inject a malformed item.json directly by pushing through a sibling clone.
        remote_url = _git(isolated_repo, "remote", "get-url", "origin")
        sibling = isolated_repo.parent / "sibling-malformed"
        if sibling.exists():
            shutil.rmtree(sibling)
        subprocess.run(
            ["git", "clone", "--branch", "bug-backlog-files",
             remote_url, str(sibling)],
            check=True, capture_output=True,
        )
        try:
            _git(sibling, "config", "user.email", "sib@test.invalid")
            _git(sibling, "config", "user.name", "Sib")
            bad_dir = (sibling / "rabbit" / "features" / "malformed-feat"
                       / "bugs" / "MALFORMED-FEAT-BUG-999")
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "item.json").write_text("{not valid json")
            _git(sibling, "add", str((bad_dir / "item.json").relative_to(sibling)))
            _git(sibling, "commit", "-m", "inject: malformed item.json")
            _git(sibling, "push", "origin", "HEAD:bug-backlog-files")
        finally:
            shutil.rmtree(sibling, ignore_errors=True)

        # read_branch should still return the valid item, and log the bad one to stderr.
        items = branch_ops.read_branch()
        captured = capsys.readouterr()

        # Valid item is still returned.
        assert any(i["name"] == id_str for i in items), (
            f"valid item should still appear in results: {items}"
        )
        # Malformed item is NOT returned.
        assert not any(i.get("name") == "MALFORMED-FEAT-BUG-999" for i in items)
        # Stderr mentions the malformed file path AND a parse-error
        # diagnostic (JSONDecodeError or similar). Silent skipping is forbidden.
        assert "MALFORMED-FEAT-BUG-999" in captured.err, (
            f"stderr must name the malformed file path; got: {captured.err!r}"
        )
        assert ("malformed" in captured.err.lower()
                or "json" in captured.err.lower()
                or "decode" in captured.err.lower()
                or "parse" in captured.err.lower()), (
            f"stderr must include a parse diagnostic; got: {captured.err!r}"
        )


# ---------------------------------------------------------------------------
# BUG-28 + BUG-30: list-items.py branch-missing distinct from no-items;
# deterministic sort order
# ---------------------------------------------------------------------------

def _run_list(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "list-items.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone),
    )


class TestListItemsBranchMissing:
    def test_branch_missing_with_filter_shows_branch_guidance(self, isolated_repo):
        """When the branch does not exist and a filter is passed, the message
        MUST direct the operator to file first (NOT 'No items found.')."""
        r = _run_list(isolated_repo, "--feature", "any-feat")
        assert r.returncode == 0
        # The fix: distinguish branch-missing from no-items.
        assert "No items found." not in r.stdout, (
            f"branch-missing must NOT print 'No items found.'; got: {r.stdout!r}"
        )
        # Operator-facing guidance.
        assert ("no items filed yet" in r.stdout.lower()
                or "branch" in r.stdout.lower()), (
            f"branch-missing must give branch guidance; got: {r.stdout!r}"
        )


class TestListItemsDeterministicSort:
    def test_output_sorted_by_name(self, isolated_repo, monkeypatch):
        """list-items.py output MUST be sorted by name (lexicographically).

        Files 3 items, then directly verifies the output ordering matches
        sorted(name) — which catches any reliance on filesystem walk order
        (rglob is generally insertion-stable in CPython but not guaranteed
        across platforms, so the script MUST sort explicitly)."""
        ids = []
        for _ in range(3):
            id_str = branch_ops.allocate_id("sort-feat", "bug")
            item = {
                "name": id_str, "type": "bug", "title": f"Item {id_str}",
                "status": "open", "priority": "low", "description": "x",
                "related_feature": "sort-feat",
                "filed": "2026-01-01T00:00:00Z", "filed_by": "t",
                "closed": None, "history": [],
            }
            branch_ops.commit_item("sort-feat", "bug", id_str, item)
            ids.append(id_str)

        r = _run_list(isolated_repo, "--feature", "sort-feat")
        assert r.returncode == 0, r.stderr
        lines = [l for l in r.stdout.strip().splitlines() if "SORT-FEAT" in l]
        names = [l.split()[0] for l in lines]
        # The list-items.py script MUST sort lexicographically by name —
        # this matches what `sorted()` does in Python.
        assert names == sorted(names), (
            f"list-items.py output must be sorted by name; got: {names}"
        )
        # And the sorted result must contain every filed item.
        assert set(names) == set(ids), (
            f"expected exactly the filed IDs {ids}, got {names}"
        )

    def test_output_sort_is_stable_across_runs(self, isolated_repo, monkeypatch):
        """Two back-to-back invocations against the same branch state MUST
        print byte-identical output."""
        for _ in range(3):
            id_str = branch_ops.allocate_id("stable-feat", "bug")
            item = {
                "name": id_str, "type": "bug", "title": f"S {id_str}",
                "status": "open", "priority": "low", "description": "x",
                "related_feature": "stable-feat",
                "filed": "2026-01-01T00:00:00Z", "filed_by": "t",
                "closed": None, "history": [],
            }
            branch_ops.commit_item("stable-feat", "bug", id_str, item)

        r1 = _run_list(isolated_repo, "--feature", "stable-feat")
        r2 = _run_list(isolated_repo, "--feature", "stable-feat")
        assert r1.returncode == 0 and r2.returncode == 0
        assert r1.stdout == r2.stdout, (
            f"list-items.py output is non-deterministic:\n"
            f"run1: {r1.stdout!r}\nrun2: {r2.stdout!r}"
        )


# ---------------------------------------------------------------------------
# BACKLOG-3: explicit allocate_id race test (in-process threads)
# ---------------------------------------------------------------------------

class TestAllocateIdRace:
    def test_subprocess_allocate_id_distinct(self, isolated_repo):
        """Two file-item.py subprocesses launched simultaneously against the
        same feature MUST produce distinct IDs. This is an explicit race
        test that complements the broader 3-way concurrent filing test in
        test-concurrent-worktree.py (BACKLOG-3)."""
        # Prime the branch so subprocesses don't race on orphan-branch init.
        branch_ops.allocate_id("race-feat", "bug")

        file_item = SCRIPTS_DIR / "file-item.py"
        env = os.environ.copy()
        procs = []
        for i in range(2):
            p = subprocess.Popen(
                [sys.executable, str(file_item),
                 "--type", "bug",
                 "--feature", "race-feat",
                 "--title", f"race {i}",
                 "--priority", "low",
                 "--description", f"race test {i}",
                 "--filed-by", "tester"],
                cwd=str(isolated_repo),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            procs.append(p)

        results = []
        for p in procs:
            out, err = p.communicate(timeout=120)
            assert p.returncode == 0, (
                f"file-item.py failed: stdout={out!r} stderr={err!r}"
            )
            results.append(out.decode())

        ids = []
        for out in results:
            for line in out.splitlines():
                if line.startswith("Filed:"):
                    ids.append(line.split()[1])
                    break
        assert len(ids) == 2
        assert len(set(ids)) == 2, (
            f"concurrent file-item.py produced duplicate IDs: {ids}"
        )


# ---------------------------------------------------------------------------
# BACKLOG-4: caller-dict-not-mutated; init-failure-cleanup; corrupted-JSON skip
# ---------------------------------------------------------------------------

class TestCallerDictNotMutated:
    def test_commit_item_does_not_mutate_caller_dict(self, isolated_repo):
        id_str = branch_ops.allocate_id("nomutate-feat", "bug")
        item = {
            "name": id_str, "type": "bug", "title": "T",
            "status": "open", "priority": "low", "description": "D",
            "related_feature": "nomutate-feat",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "t",
            "closed": None, "history": [],
        }
        snapshot = dict(item)
        branch_ops.commit_item("nomutate-feat", "bug", id_str, item)
        # The caller's dict MUST be unchanged (no commit_sha leaked back).
        assert item == snapshot, (
            f"caller dict was mutated. before={snapshot}, after={item}"
        )
        assert "commit_sha" not in item


class TestCorruptedJsonSkipReturnsValidItems:
    def test_read_branch_skips_corrupted_returns_valid(self, isolated_repo,
                                                       capsys):
        # File two valid items.
        ids = []
        for i in range(2):
            id_str = branch_ops.allocate_id("corrupt-feat", "bug")
            item = {
                "name": id_str, "type": "bug", "title": f"v{i}",
                "status": "open", "priority": "low", "description": "x",
                "related_feature": "corrupt-feat",
                "filed": "2026-01-01T00:00:00Z", "filed_by": "t",
                "closed": None, "history": [],
            }
            branch_ops.commit_item("corrupt-feat", "bug", id_str, item)
            ids.append(id_str)

        # Inject corruption via sibling.
        remote_url = _git(isolated_repo, "remote", "get-url", "origin")
        sibling = isolated_repo.parent / "sibling-corrupt"
        if sibling.exists():
            shutil.rmtree(sibling)
        subprocess.run(
            ["git", "clone", "--branch", "bug-backlog-files",
             remote_url, str(sibling)],
            check=True, capture_output=True,
        )
        try:
            _git(sibling, "config", "user.email", "sib@test.invalid")
            _git(sibling, "config", "user.name", "Sib")
            bad_dir = (sibling / "rabbit" / "features" / "corrupt-feat"
                       / "bugs" / "CORRUPT-FEAT-BUG-998")
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "item.json").write_text("nope")
            _git(sibling, "add", str((bad_dir / "item.json").relative_to(sibling)))
            _git(sibling, "commit", "-m", "inject corrupt")
            _git(sibling, "push", "origin", "HEAD:bug-backlog-files")
        finally:
            shutil.rmtree(sibling, ignore_errors=True)

        items = branch_ops.read_branch(feature="corrupt-feat")
        # Both valid items returned; corrupt item skipped.
        valid_names = {i["name"] for i in items}
        for valid_id in ids:
            assert valid_id in valid_names
        assert "CORRUPT-FEAT-BUG-998" not in valid_names


class TestInitFailureCleanup:
    def test_orphan_init_tmp_cleaned_on_failure(self, isolated_repo,
                                                 monkeypatch):
        """If _init_orphan_branch raises midway, the tmp/branch-init-tmp
        directory MUST still be cleaned up (try/finally)."""
        # Force _git inside _init_orphan_branch to fail on the push step.
        original_git = branch_ops._git

        def maybe_failing_git(repo, *args):
            if "push" in args and "branch-init-tmp" in str(repo):
                raise RuntimeError("simulated init push failure")
            return original_git(repo, *args)

        monkeypatch.setattr(branch_ops, "_git", maybe_failing_git)

        with pytest.raises(RuntimeError, match="simulated init push failure"):
            branch_ops._init_orphan_branch(str(isolated_repo))

        tmp = Path(isolated_repo) / ".claude" / "tmp" / "branch-init-tmp"
        assert not tmp.exists(), (
            f"branch-init-tmp was not cleaned up after init failure: {tmp}"
        )


# ---------------------------------------------------------------------------
# BACKLOG-7: item-status update length validation
# ---------------------------------------------------------------------------

@pytest.fixture
def filed_item(isolated_repo, monkeypatch):
    id_str = branch_ops.allocate_id("len-feat", "bug")
    item = {
        "name": id_str, "type": "bug", "title": "T",
        "status": "open", "priority": "high", "description": "D",
        "related_feature": "len-feat",
        "filed": "2026-01-01T00:00:00Z", "filed_by": "t",
        "closed": None, "history": [],
    }
    branch_ops.commit_item("len-feat", "bug", id_str, item)
    return isolated_repo, id_str


def _run_status(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "item-status.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone),
    )


class TestUpdateLengthValidation:
    # BACKLOG-7: the shared 500-char cap was replaced with per-field limits
    # (title=200, description=10240). Detailed coverage of the new boundaries
    # lives in test-RABBIT-FILE-BACKLOG-7-per-field-limits.py; the smoke tests
    # below pin the high-level contract here so it stays visible from this
    # historical suite.
    def test_title_over_200_chars_rejected(self, filed_item):
        clone, id_str = filed_item
        long_title = "x" * 201
        r = _run_status(clone, "update", "--feature", "len-feat", "--type", "bug",
                        "--id", id_str, "--field", "title", "--value", long_title,
                        "--reason", "test")
        assert r.returncode == 1, r.stderr
        assert "200" in r.stderr
        assert "title" in r.stderr

    def test_description_over_10240_chars_rejected(self, filed_item):
        clone, id_str = filed_item
        long_desc = "y" * 10241
        r = _run_status(clone, "update", "--feature", "len-feat", "--type", "bug",
                        "--id", id_str, "--field", "description", "--value", long_desc,
                        "--reason", "test")
        assert r.returncode == 1, r.stderr
        assert "10240" in r.stderr
        assert "description" in r.stderr

    def test_title_at_200_chars_accepted(self, filed_item):
        clone, id_str = filed_item
        ok_title = "z" * 200
        r = _run_status(clone, "update", "--feature", "len-feat", "--type", "bug",
                        "--id", id_str, "--field", "title", "--value", ok_title,
                        "--reason", "boundary")
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# BACKLOG-8: item-status show subcommand
# ---------------------------------------------------------------------------

class TestShowSubcommand:
    def test_show_prints_full_item_json(self, filed_item):
        clone, id_str = filed_item
        r = _run_status(clone, "show", "--feature", "len-feat", "--type", "bug",
                        "--id", id_str)
        assert r.returncode == 0, r.stderr
        # Output is valid JSON.
        parsed = json.loads(r.stdout)
        assert parsed["name"] == id_str
        assert parsed["type"] == "bug"
        assert parsed["priority"] == "high"
        # Includes history.
        assert "history" in parsed
        # Includes commit_sha (backfilled).
        assert "commit_sha" in parsed

    def test_show_missing_item_exits_nonzero(self, isolated_repo):
        r = _run_status(isolated_repo, "show", "--feature", "absent",
                        "--type", "bug", "--id", "ABSENT-BUG-99")
        assert r.returncode == 1, r.stdout
        assert "not found" in r.stderr.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
