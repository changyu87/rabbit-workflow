"""Shared rabbit-cage test fixtures (BACKLOG-13).

Eight test files independently rebuilt the same minimal-repo skeleton
(`make_clean_repo` / `build_tmproot_clean` / `make_build_repo`). Centralise
the skeleton here so spec changes (e.g., a new required policy file) update
in one place instead of eight.

Public helpers:

  REPO_ROOT          — absolute path of the live repo root (git rev-parse).
  make_clean_repo()  — temp dir holding a minimal cage-compatible workspace
                       (no git init).
  make_git_repo()    — like make_clean_repo() but with `git init` + initial
                       commit on branch `main`.
  run_sync(tmproot, **env_overrides) — run the live sync-check.py against the
                       sandbox and return its stdout string.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

# Single source of truth for REPO_ROOT (BUG-64 follow-on): every caller
# delegating to this helper inherits the git rev-parse derivation.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", _THIS_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

CAGE_SCRIPTS = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts")
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")

_DEFAULT_POLICY = [
    ("philosophy.md", "# Philosophy\nMachine First.\n"),
    ("spec-rules.md", "# Spec Rules\nSpec.\n"),
    ("coding-rules.md", "# Coding Rules\nCode.\n"),
]


def _populate(tmproot, policy_files=None):
    """Lay down the minimal skeleton inside an existing dir."""
    policy_files = policy_files or _DEFAULT_POLICY
    os.makedirs(os.path.join(tmproot, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(tmproot, ".claude/features/policy"), exist_ok=True)

    for fname, content in policy_files:
        with open(os.path.join(tmproot, ".claude/features/policy", fname), "w") as f:
            f.write(content)

    with open(os.path.join(tmproot, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test header"}, f)

    for fname in ("generate-claude-md.py", "generate-claude-md-header.py"):
        shutil.copy(
            os.path.join(CAGE_SCRIPTS, fname),
            os.path.join(tmproot, ".claude/features/rabbit-cage/scripts", fname),
        )

    with open(os.path.join(tmproot, ".claude/features/registry.json"), "w") as f:
        json.dump({"schema_version": "1.0.0", "features": {}}, f)

    env = {**os.environ, "RABBIT_ROOT": tmproot}
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md.py"),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write(result.stdout.rstrip("\n") + "\n")


def make_clean_repo(policy_files=None):
    """Temp directory holding the minimal cage skeleton; no git init."""
    tmproot = tempfile.mkdtemp(prefix="cage-test-")
    _populate(tmproot, policy_files)
    return tmproot


def make_git_repo(policy_files=None):
    """Like make_clean_repo() plus `git init` + an initial commit on main."""
    tmproot = tempfile.mkdtemp(prefix="cage-test-git-")
    subprocess.run(["git", "init", "-q", tmproot], check=True)
    subprocess.run(
        ["git", "-C", tmproot, "config", "user.email", "test@test.com"], check=True,
    )
    subprocess.run(
        ["git", "-C", tmproot, "config", "user.name", "Test"], check=True,
    )
    subprocess.run(
        ["git", "-C", tmproot, "checkout", "-q", "-b", "main"], capture_output=True,
    )
    _populate(tmproot, policy_files)
    subprocess.run(
        ["git", "-C", tmproot, "add", "-A"], check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", tmproot, "commit", "-q", "-m", "init"],
        check=True, capture_output=True,
    )
    return tmproot


def run_sync(tmproot, **env_overrides):
    """Run the live sync-check.py against the sandbox; return stdout."""
    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    env.update({k: str(v) for k, v in env_overrides.items()})
    result = subprocess.run(
        [sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True,
    )
    return result.stdout
