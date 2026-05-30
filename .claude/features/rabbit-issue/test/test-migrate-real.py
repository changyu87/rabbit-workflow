"""migrate.py — real migration path.

Verifies that running migrate.py (no `--dry-run`) against the synthetic
origin/bug-backlog-files branch:
  - calls `gh issue create` once per open item (2 in the fixture)
  - writes the closed item to archive/bug-backlog/<feature>/<id>.json
  - writes archive/migration-manifest.json with all migrated items tracked
  - maps the old `backlog` type to GH's `enhancement` label
"""
import json
import subprocess
import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MIGRATE = SCRIPTS / "migrate.py"


def _setup(fake_repo):
    # Reuse the synthetic-branch helper from the dry-run test module.
    # Importing by file path because the module name contains hyphens.
    spec = spec_from_file_location(
        "dry_test", Path(__file__).parent / "test-migrate-dry-run.py"
    )
    m = module_from_spec(spec)
    spec.loader.exec_module(m)
    m.setup_synthetic_branch(fake_repo)


def test_real_migration_creates_issues_and_archives(gh_shim, fake_repo):
    _setup(fake_repo)
    r = subprocess.run(
        [sys.executable, str(MIGRATE)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    # 2 open items → 2 `issue create` calls
    assert log.count("issue create") == 2
    # 1 closed item → archive file present
    archive = fake_repo / "archive/bug-backlog/rabbit-cage/RABBIT-CAGE-BUG-2.json"
    assert archive.is_file()
    # Manifest exists and tracks all items
    manifest = json.loads(
        (fake_repo / "archive/migration-manifest.json").read_text()
    )
    assert len(manifest["open_items"]) == 2
    assert len(manifest["closed_items"]) == 1


def test_backlog_type_mapped_to_enhancement(gh_shim, fake_repo):
    _setup(fake_repo)
    r = subprocess.run(
        [sys.executable, str(MIGRATE)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    log = gh_shim.read_text()
    create_lines = [
        line for line in log.split("\n") if line.startswith("issue create")
    ]
    # Exactly one of the two creates should carry the `enhancement` label.
    enhancement_lines = [line for line in create_lines if "enhancement" in line]
    bug_lines = [
        line for line in create_lines
        if ",bug," in line or line.endswith(",bug") or "label bug," in line
    ]
    assert len(enhancement_lines) == 1
    assert len(bug_lines) == 1


def test_real_migration_prints_ready_to_delete_footer(gh_shim, fake_repo):
    _setup(fake_repo)
    r = subprocess.run(
        [sys.executable, str(MIGRATE)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "READY TO DELETE BRANCH" in r.stdout
    assert "git push origin --delete bug-backlog-files" in r.stdout
    # Must NOT actually execute the delete — gh_shim never sees it (gh has no
    # `push` subcommand anyway), and the local refs/remotes/origin/bug-backlog-files
    # ref must still exist.
    ref = subprocess.run(
        ["git", "-C", str(fake_repo), "rev-parse",
         "refs/remotes/origin/bug-backlog-files"],
        capture_output=True, text=True,
    )
    assert ref.returncode == 0
