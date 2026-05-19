"""
Shared pytest helpers for the rabbit-file test suite.

`seed_bug_backlog_branch(bare_remote)` pre-creates the
`bug-backlog-files` branch on a bare git remote with an empty initial
commit. This mirrors the real-world setup where the branch already
exists upstream (on GitHub) before any rabbit-file operation runs.

It is REQUIRED for fixtures that use a local bare repo as `origin`:
since BUG-32, `_ensure_branch` refuses to orphan-bootstrap when origin
is a local filesystem path (to avoid silently overwriting upstream
items in chained-workspace topologies). Pre-seeding sidesteps that
guard the same way production does — by ensuring the branch exists
before the first call.
"""

import os
import shutil
import subprocess
from pathlib import Path


def seed_bug_backlog_branch(bare_remote: Path) -> None:
    """Push an empty orphan `bug-backlog-files` commit to `bare_remote`."""
    seed = Path(str(bare_remote) + ".seed-tmp")
    if seed.exists():
        shutil.rmtree(seed)
    subprocess.run(
        ["git", "clone", str(bare_remote), str(seed)],
        check=True, capture_output=True,
    )
    try:
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = "seed"
        env["GIT_AUTHOR_EMAIL"] = "seed@test.invalid"
        env["GIT_COMMITTER_NAME"] = "seed"
        env["GIT_COMMITTER_EMAIL"] = "seed@test.invalid"
        subprocess.run(
            ["git", "-C", str(seed), "checkout", "--orphan", "bug-backlog-files"],
            check=True, capture_output=True, env=env,
        )
        subprocess.run(
            ["git", "-C", str(seed), "commit", "--allow-empty",
             "-m", "init: orphan branch"],
            check=True, capture_output=True, env=env,
        )
        subprocess.run(
            ["git", "-C", str(seed), "push", "origin", "HEAD:bug-backlog-files"],
            check=True, capture_output=True, env=env,
        )
    finally:
        shutil.rmtree(seed, ignore_errors=True)
