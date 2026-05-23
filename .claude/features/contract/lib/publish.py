"""contract.lib.publish — API library for deploying feature artifacts to the workspace.

Each function implements one publish API call as declared in a feature's MANIFEST
section. All functions accept API args as explicit params plus keyword-only context
params (feature_dir, repo_root) and return CheckResult.

All publish operations are idempotent: if the destination already matches the source
(by SHA-256 for files, by content equality for generated), the call is a no-op.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native artifact publishing.
"""

import hashlib
import os
import shutil
from pathlib import Path

from lib.checks import CheckResult


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def publish_file(source: str, dest: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy source (feature-dir-relative) to dest (repo-root-relative), idempotent.

    Returns CheckResult(passed=False) if source does not exist.
    Returns CheckResult(passed=True) on success (copy) or no-op (unchanged).
    """
    src_path = os.path.join(feature_dir, source)
    dst_path = os.path.join(repo_root, dest)
    if not os.path.isfile(src_path):
        return CheckResult(False, [f"ERROR: source not found: {src_path}"])
    if os.path.isfile(dst_path) and _sha256_file(src_path) == _sha256_file(dst_path):
        return CheckResult(True, [f"OK: {dest} unchanged (no-op)"])
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy(src_path, dst_path)
    return CheckResult(True, [f"OK: {dest} published"])


def publish_skill(source: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy a skill's SKILL.md to .claude/skills/<skill-name>/SKILL.md.

    source — feature-dir-relative path, e.g. "skills/rabbit-foo/SKILL.md".
    Skill name is the name of the source file's parent directory.
    """
    skill_name = Path(source).parent.name
    dest = f".claude/skills/{skill_name}/{Path(source).name}"
    return publish_file(source, dest, feature_dir=feature_dir, repo_root=repo_root)


def publish_command(source: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy a command file to .claude/commands/<basename>.

    source — feature-dir-relative path, e.g. "commands/rabbit-do.md".
    """
    dest = f".claude/commands/{Path(source).name}"
    return publish_file(source, dest, feature_dir=feature_dir, repo_root=repo_root)


def publish_agent(source: str, *, feature_dir: str, repo_root: str) -> CheckResult:
    """Deploy an agent file to .claude/agents/<basename>.

    source — feature-dir-relative path, e.g. "agents/rabbit-helper.md".
    """
    dest = f".claude/agents/{Path(source).name}"
    return publish_file(source, dest, feature_dir=feature_dir, repo_root=repo_root)
