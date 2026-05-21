#!/usr/bin/env python3
"""E2E tests for Invariant 19 (Team-wide Permissions).

Verifies that:
  (a) the source file .claude/features/rabbit-cage/settings.json declares the
      team-wide `permissions` block exactly as specified in Inv 19;
  (b) the build-managed copy at .claude/settings.json contains the same block
      after running build.py (verifying copy-file propagation);
  (c) no other top-level keys (env, hooks) are removed by the new key.

Inv 44: this test MUST NOT mutate live source files. The E2E
propagation test (case (b) E2E) runs inside an isolated temp repo mirror so
even an interrupted test cannot corrupt the live worktree.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", "..", ".."))
SOURCE_SETTINGS = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-cage", "settings.json"
)
DEST_SETTINGS = os.path.join(REPO_ROOT, ".claude", "settings.json")
BUILD_PY = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-cage", "scripts", "build.py"
)
BUILD_TARGETS_PY = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-cage", "scripts", "build-targets.py"
)
BUILD_CONTRACT = os.path.join(
    REPO_ROOT, ".claude", "features", "contract", "build-contract.json"
)

EXPECTED_ALLOW = ["Bash(*)", "Write", "Edit"]
EXPECTED_DENY = [
    "Bash(git merge *)",
    "Bash(git push * main)",
    "Bash(git push origin main)",
]


def _load(path):
    with open(path) as f:
        return json.load(f)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_source_settings_has_permissions_block():
    """Inv 19: source settings.json declares the exact permissions block."""
    data = _load(SOURCE_SETTINGS)
    assert "permissions" in data, "source settings.json missing 'permissions' key"
    perms = data["permissions"]
    assert isinstance(perms, dict), f"permissions must be object, got {type(perms)}"
    assert perms.get("allow") == EXPECTED_ALLOW, (
        f"permissions.allow must be exactly {EXPECTED_ALLOW}, got {perms.get('allow')!r}"
    )
    assert perms.get("deny") == EXPECTED_DENY, (
        f"permissions.deny must be exactly {EXPECTED_DENY}, got {perms.get('deny')!r}"
    )


def test_source_settings_allow_order_is_exact():
    """Inv 19 (v2.9.0): allow must contain exactly Bash(*), Write, Edit in that order."""
    data = _load(SOURCE_SETTINGS)
    allow = data["permissions"]["allow"]
    assert allow == ["Bash(*)", "Write", "Edit"], (
        f"allow order must be [Bash(*), Write, Edit], got {allow!r}"
    )


def test_destination_settings_allow_order_is_exact():
    """Inv 19 (v2.9.0): build-managed copy must hold the same ordered allow list."""
    data = _load(DEST_SETTINGS)
    allow = data["permissions"]["allow"]
    assert allow == ["Bash(*)", "Write", "Edit"], (
        f"dest allow order must be [Bash(*), Write, Edit], got {allow!r}"
    )


def test_source_settings_preserves_env_and_hooks():
    """Inv 19 mandate: 'No other top-level keys (env, hooks) are altered.'"""
    data = _load(SOURCE_SETTINGS)
    assert "env" in data, "source settings.json must still contain 'env'"
    assert "hooks" in data, "source settings.json must still contain 'hooks'"
    assert data["env"].get("RABBIT_REFRESH_EVERY") == "20", (
        "RABBIT_REFRESH_EVERY default must remain '20'"
    )
    hooks = data["hooks"]
    for key in ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop"):
        assert key in hooks, f"hooks.{key} missing from source settings.json"


def test_destination_settings_holds_same_permissions_block():
    """Inv 19: .claude/settings.json (build-managed copy) holds the same block."""
    data = _load(DEST_SETTINGS)
    assert "permissions" in data, ".claude/settings.json missing 'permissions' key"
    perms = data["permissions"]
    assert perms.get("allow") == EXPECTED_ALLOW, (
        f"dest permissions.allow must be {EXPECTED_ALLOW}, got {perms.get('allow')!r}"
    )
    assert perms.get("deny") == EXPECTED_DENY, (
        f"dest permissions.deny must be {EXPECTED_DENY}, got {perms.get('deny')!r}"
    )


def test_build_py_propagates_permissions_e2e_sandboxed():
    """E2E (sandboxed): mutate sandbox source, run build, observe propagation.

    Inv 44: runs entirely inside a temp-dir mirror so a crashed test cannot
    leave the live worktree corrupted. We copy SOURCE_SETTINGS, build.py,
    build-targets.py, and the build-contract into a tmp tree under the same
    relative layout, mutate the sandbox source, and verify build-targets.py
    propagates the change to the sandbox destination.
    """
    sandbox = tempfile.mkdtemp(prefix="test-team-wide-permissions-")
    try:
        # Reproduce minimal layout build-targets.py needs. Source/destination
        # in the contract are repo-relative (build-targets.py prepends
        # repo_root). Use the sandbox as repo_root.
        src_rel = "src/settings.json"
        dst_rel = ".claude/settings.json"
        sandbox_src = os.path.join(sandbox, src_rel)
        sandbox_dst = os.path.join(sandbox, dst_rel)
        os.makedirs(os.path.dirname(sandbox_src), exist_ok=True)
        os.makedirs(os.path.dirname(sandbox_dst), exist_ok=True)
        shutil.copy(SOURCE_SETTINGS, sandbox_src)

        # Mutate sandbox source: add probe deny.
        data = json.loads(open(sandbox_src).read())
        probe = "Bash(test-probe-do-not-keep)"
        data["permissions"]["deny"].append(probe)
        with open(sandbox_src, "w") as f:
            json.dump(data, f, indent=2)

        contract = {
            "schema_version": "1.0.0",
            "targets": [
                {
                    "name": "settings.json",
                    "type": "copy-file",
                    "source": src_rel,
                    "destination": dst_rel,
                    "check_on_stop": False,
                }
            ],
        }
        contract_path = os.path.join(sandbox, "build-contract.json")
        with open(contract_path, "w") as f:
            json.dump(contract, f, indent=2)

        # Run build-targets.py against the sandbox.
        env = {**os.environ, "RABBIT_ROOT": sandbox}
        # Use the live build-targets.py but with sandbox root.
        result = subprocess.run(
            [sys.executable, BUILD_TARGETS_PY, sandbox, contract_path,
             os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
            cwd=sandbox,
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, (
            f"build-targets.py failed: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        new_dest = json.loads(open(sandbox_dst).read())
        assert probe in new_dest.get("permissions", {}).get("deny", []), (
            "build-targets.py did not propagate the probe deny entry in sandbox — "
            "copy-file propagation broken for permissions"
        )
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def test_inv64_live_source_files_unchanged():
    """Inv 44: this test must not have mutated any live source file.

    Run last; compares snapshots taken at module import vs current state.
    """
    post = _sha(SOURCE_SETTINGS)
    assert post == _PRE_SOURCE_SHA, (
        f"Inv 44 violation: SOURCE_SETTINGS sha changed during test "
        f"(pre={_PRE_SOURCE_SHA}, post={post})"
    )
    post_dest = _sha(DEST_SETTINGS)
    assert post_dest == _PRE_DEST_SHA, (
        f"Inv 44 violation: DEST_SETTINGS sha changed during test "
        f"(pre={_PRE_DEST_SHA}, post={post_dest})"
    )


# Snapshot live source state at import time for the Inv 44 check.
_PRE_SOURCE_SHA = _sha(SOURCE_SETTINGS) if os.path.isfile(SOURCE_SETTINGS) else ""
_PRE_DEST_SHA = _sha(DEST_SETTINGS) if os.path.isfile(DEST_SETTINGS) else ""


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
