"""migrate.py — idempotency.

Second run against the same synthetic branch + persisted manifest must
add zero new `gh issue create` calls and zero new archive files. The
manifest is the source of truth for what has already been migrated.
"""
import json
import subprocess
import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MIGRATE = SCRIPTS / "migrate.py"


def _setup(fake_repo):
    spec = spec_from_file_location(
        "dry_test", Path(__file__).parent / "test-migrate-dry-run.py"
    )
    m = module_from_spec(spec)
    spec.loader.exec_module(m)
    m.setup_synthetic_branch(fake_repo)


def test_second_run_is_noop(gh_shim, fake_repo):
    _setup(fake_repo)
    # First run
    r1 = subprocess.run(
        [sys.executable, str(MIGRATE)],
        capture_output=True, text=True,
    )
    assert r1.returncode == 0, r1.stderr
    create_count_1 = gh_shim.read_text().count("issue create")
    manifest_1 = json.loads(
        (fake_repo / "archive/migration-manifest.json").read_text()
    )

    # Second run
    r2 = subprocess.run(
        [sys.executable, str(MIGRATE)],
        capture_output=True, text=True,
    )
    assert r2.returncode == 0, r2.stderr
    create_count_2 = gh_shim.read_text().count("issue create")
    manifest_2 = json.loads(
        (fake_repo / "archive/migration-manifest.json").read_text()
    )

    # No new issue creates and manifest counts identical.
    assert create_count_2 == create_count_1
    assert len(manifest_2["open_items"]) == len(manifest_1["open_items"])
    assert len(manifest_2["closed_items"]) == len(manifest_1["closed_items"])
