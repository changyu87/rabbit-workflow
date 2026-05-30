"""migrate.py — dry-run mode.

Verifies that `--dry-run`:
  - reports open / closed counts walked from origin/bug-backlog-files
  - performs zero writes (no gh issue create, no archive/, no manifest)

The synthetic-branch helper builds 2 open + 1 closed item.json files on
an orphan branch and points refs/remotes/origin/bug-backlog-files at it
so migrate.py's `git ls-tree origin/bug-backlog-files` walk succeeds.
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MIGRATE = SCRIPTS / "migrate.py"


def setup_synthetic_branch(fake_repo):
    """Create a synthetic origin/bug-backlog-files with 2 open + 1 closed items.

    Layout written into the orphan branch:
      rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-1/item.json   (open bug)
      rabbit/features/rabbit-cage/backlogs/RABBIT-CAGE-BACKLOG-1/item.json (open backlog)
      rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-2/item.json   (closed bug)
    """
    repo = fake_repo
    subprocess.run(
        ["git", "-C", str(repo), "checkout", "--orphan", "bug-backlog-files"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "rm", "-rf", "--ignore-unmatch", "."],
        check=True,
    )
    items = [
        ("rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-1", {
            "name": "RABBIT-CAGE-BUG-1", "type": "bug", "status": "open",
            "title": "t1", "priority": "high", "description": "d1",
            "related_feature": "rabbit-cage",
        }),
        ("rabbit/features/rabbit-cage/backlogs/RABBIT-CAGE-BACKLOG-1", {
            "name": "RABBIT-CAGE-BACKLOG-1", "type": "backlog", "status": "open",
            "title": "t2", "priority": "low", "description": "d2",
            "related_feature": "rabbit-cage",
        }),
        ("rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-2", {
            "name": "RABBIT-CAGE-BUG-2", "type": "bug", "status": "close",
            "title": "t3", "priority": "medium", "description": "d3",
            "related_feature": "rabbit-cage",
        }),
    ]
    for rel, body in items:
        d = repo / rel
        d.mkdir(parents=True)
        (d / "item.json").write_text(json.dumps(body))
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "synthetic"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "update-ref",
         "refs/remotes/origin/bug-backlog-files", "HEAD"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "checkout", "-q", "-b", "main"],
        check=True,
    )


def test_dry_run_reports_counts_without_writes(gh_shim, fake_repo):
    setup_synthetic_branch(fake_repo)
    r = subprocess.run(
        [sys.executable, str(MIGRATE), "--dry-run"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout.lower()
    assert "open items:" in out and "2" in out
    assert "closed items:" in out and "1" in out
    # No GH writes
    log = gh_shim.read_text()
    assert "issue create" not in log
    assert "label create" not in log
    # No archive writes
    assert not (fake_repo / "archive").exists()
