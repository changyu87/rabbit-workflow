#!/usr/bin/env python3
"""E2E tests for Invariant 51 (Team-wide Permissions).

Verifies that:
  (a) the source file .claude/features/rabbit-cage/settings.json declares the
      team-wide `permissions` block exactly as specified in Inv 51;
  (b) the build-managed copy at .claude/settings.json contains the same block
      after running build.py (verifying copy-file propagation);
  (c) no other top-level keys (env, hooks) are removed by the new key.
"""
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

EXPECTED_ALLOW = ["Bash(*)", "Write", "Edit"]
EXPECTED_DENY = [
    "Bash(git merge *)",
    "Bash(git push * main)",
    "Bash(git push origin main)",
]


def _load(path):
    with open(path) as f:
        return json.load(f)


def test_source_settings_has_permissions_block():
    """Inv 51: source settings.json declares the exact permissions block."""
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
    """Inv 51 (v2.9.0): allow must contain exactly Bash(*), Write, Edit in that order."""
    data = _load(SOURCE_SETTINGS)
    allow = data["permissions"]["allow"]
    # Exact list equality (order-sensitive) already enforced above; this test
    # asserts the spec's "in that order" requirement explicitly as a separate
    # behaviour so a regression to alphabetical / set-based output is obvious.
    assert allow == ["Bash(*)", "Write", "Edit"], (
        f"allow order must be [Bash(*), Write, Edit], got {allow!r}"
    )


def test_destination_settings_allow_order_is_exact():
    """Inv 51 (v2.9.0): build-managed copy must hold the same ordered allow list."""
    data = _load(DEST_SETTINGS)
    allow = data["permissions"]["allow"]
    assert allow == ["Bash(*)", "Write", "Edit"], (
        f"dest allow order must be [Bash(*), Write, Edit], got {allow!r}"
    )


def test_source_settings_preserves_env_and_hooks():
    """Inv 51 mandate: 'No other top-level keys (env, hooks) are altered.'"""
    data = _load(SOURCE_SETTINGS)
    assert "env" in data, "source settings.json must still contain 'env'"
    assert "hooks" in data, "source settings.json must still contain 'hooks'"
    assert data["env"].get("RABBIT_REFRESH_EVERY") == "20", (
        "RABBIT_REFRESH_EVERY default must remain '20'"
    )
    # Hooks block must still contain the four expected matchers
    hooks = data["hooks"]
    for key in ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop"):
        assert key in hooks, f"hooks.{key} missing from source settings.json"


def test_destination_settings_holds_same_permissions_block():
    """Inv 51: .claude/settings.json (build-managed copy) holds the same block."""
    data = _load(DEST_SETTINGS)
    assert "permissions" in data, ".claude/settings.json missing 'permissions' key"
    perms = data["permissions"]
    assert perms.get("allow") == EXPECTED_ALLOW, (
        f"dest permissions.allow must be {EXPECTED_ALLOW}, got {perms.get('allow')!r}"
    )
    assert perms.get("deny") == EXPECTED_DENY, (
        f"dest permissions.deny must be {EXPECTED_DENY}, got {perms.get('deny')!r}"
    )


def test_build_py_propagates_permissions_e2e():
    """E2E: editing source then running build.py mirrors the change into dest.

    This proves the copy-file propagation works for the new permissions key —
    the core invariant guarantee that 'team-wide defaults live in the source
    so build rebuilds propagate them' (Inv 51 + Inv 50)."""
    # Snapshot original files so we can restore them.
    with open(SOURCE_SETTINGS) as f:
        original_source = f.read()
    with open(DEST_SETTINGS) as f:
        original_dest = f.read()

    try:
        # Mutate the source: add an extra deny entry as a probe.
        data = json.loads(original_source)
        probe = "Bash(test-probe-do-not-keep)"
        data["permissions"]["deny"].append(probe)
        with open(SOURCE_SETTINGS, "w") as f:
            json.dump(data, f, indent=2)

        # Run build.py — this should propagate the source to destination.
        result = subprocess.run(
            [sys.executable, BUILD_PY],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"build.py failed: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # Destination should now contain the probe entry.
        new_dest = _load(DEST_SETTINGS)
        assert probe in new_dest.get("permissions", {}).get("deny", []), (
            "build.py did not propagate the probe deny entry from source to "
            ".claude/settings.json — copy-file propagation broken for permissions"
        )
    finally:
        # Restore original source and re-run build to restore destination cleanly.
        with open(SOURCE_SETTINGS, "w") as f:
            f.write(original_source)
        subprocess.run(
            [sys.executable, BUILD_PY],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # As a belt-and-suspenders restore, also rewrite destination from snapshot
        # in case build had a side effect. (build.py should produce identical
        # content from identical source; this is purely defensive.)
        with open(DEST_SETTINGS, "w") as f:
            f.write(original_dest)


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
