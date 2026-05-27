#!/usr/bin/env python3
"""E2E tests for Invariants 17 and 18: scope-guard plugin-mode decision
tree and one-shot bypass-once marker.

Operates against the actual REPO_ROOT (scope-guard.py resolves REPO_ROOT
at module load time from its own location, so it always points at the
rabbit-workflow repo). The tests save and restore the runtime markers
they touch under .rabbit/.runtime/ and .rabbit/rabbit-project/ so they
do not leak state across runs.

Tests:
  t1: standalone mode (no mode file)            -> behavior unchanged
  t2: plugin mode, no project-map.json          -> user-code edits ALLOW
  t3: plugin mode + declared path + marker      -> ALLOW
  t4: plugin mode + declared path + NO marker   -> DENY with structured msg
  t5: plugin mode + .rabbit/.claude/** edit     -> DENY always
  t6: bypass-once marker present                -> ALLOW + marker deleted
  t7: bypass-once + DENY path                   -> ALLOW + marker still deleted
                                                   (consume-before-evaluate)
  t8: scope-bypass-once path itself allowlisted -> ALLOW
"""
import contextlib
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")

RUNTIME_DIR = os.path.join(REPO_ROOT, ".rabbit", ".runtime")
MAP_DIR = os.path.join(REPO_ROOT, ".rabbit", "rabbit-project")
MODE_FILE = os.path.join(RUNTIME_DIR, "mode")
MAP_FILE = os.path.join(MAP_DIR, "project-map.json")
BYPASS_FILE = os.path.join(RUNTIME_DIR, "scope-bypass-once")
OVERRIDE_FILE = os.path.join(REPO_ROOT, ".rabbit-scope-override")
OVERRIDE_USED = os.path.join(REPO_ROOT, ".rabbit-scope-override-used")

# A throwaway "feature path" we own for testing — under .claude/features
# so we don't pollute user source. Use a non-existent dir under our
# feature so we're not creating actual user code.
TEST_FEATURE_NAME = "rabbit-cage-plugin-test-feature"
TEST_PATH_GLOB = ".claude/features/rabbit-cage/test/__plugin_mode_synthetic__/**"
TEST_TARGET = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/test/__plugin_mode_synthetic__/x.py"
)

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


@contextlib.contextmanager
def saved_state():
    """Snapshot and restore all runtime files this test touches."""
    paths = [MODE_FILE, MAP_FILE, BYPASS_FILE, OVERRIDE_FILE, OVERRIDE_USED]
    paths.extend(
        os.path.join(RUNTIME_DIR, n) for n in os.listdir(RUNTIME_DIR)
        if os.path.isdir(RUNTIME_DIR) and n.startswith("scope-active-")
    ) if os.path.isdir(RUNTIME_DIR) else None
    saved = {}
    for p in paths:
        if os.path.isfile(p):
            with open(p, "rb") as f:
                saved[p] = f.read()
            os.remove(p)
    # Also clear the synthetic test target if present
    if os.path.exists(TEST_TARGET):
        os.remove(TEST_TARGET)
    try:
        yield
    finally:
        # Cleanup any files this test created
        for p in [MODE_FILE, MAP_FILE, BYPASS_FILE, OVERRIDE_FILE, OVERRIDE_USED]:
            if os.path.isfile(p):
                os.remove(p)
        if os.path.isdir(RUNTIME_DIR):
            for n in os.listdir(RUNTIME_DIR):
                if n.startswith("scope-active-"):
                    os.remove(os.path.join(RUNTIME_DIR, n))
        # Restore originals
        for p, content in saved.items():
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(content)


def write_mode(content):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(MODE_FILE, "w") as f:
        f.write(content)


def write_project_map(mapping):
    os.makedirs(MAP_DIR, exist_ok=True)
    with open(MAP_FILE, "w") as f:
        json.dump(mapping, f)


def write_scope_active(name):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    p = os.path.join(RUNTIME_DIR, f"scope-active-{name}")
    with open(p, "w") as f:
        f.write("")


def write_bypass_once():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(BYPASS_FILE, "w") as f:
        f.write("")


def run_guard(target_path):
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": target_path, "content": "x"}}
    result = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return result.returncode, result.stderr


print("test-scope-guard-plugin-mode.py")
print()

# ---------------------------------------------------------------- t1
print("=== t1: standalone mode (no mode file) — behavior unchanged ===")
with saved_state():
    # No mode file written → standalone branch. Default-deny on a path
    # that has no scope marker and isn't on the allowlist. Use a target
    # in a different feature (policy) so the active rabbit-cage marker
    # does not extend coverage. Then assert the standalone DENY surfaces.
    other_target = os.path.join(
        REPO_ROOT, ".claude/features/policy/__plugin_mode_test_target__.txt"
    )
    rc, stderr = run_guard(other_target)
    if rc == 2 and "DENY" in stderr and "SESSION OVERRIDE" in stderr:
        ok("standalone default-deny still produces structured DENY")
    else:
        fail_t(f"standalone behavior changed: rc={rc} stderr={stderr!r}")

# ---------------------------------------------------------------- t2
print()
print("=== t2: plugin mode + no project-map.json → user-code ALLOW ===")
with saved_state():
    write_mode("plugin")
    rc, stderr = run_guard(TEST_TARGET)
    if rc == 0:
        ok("no project-map → user-code edit ALLOWED (default safe)")
    else:
        fail_t(f"expected ALLOW (rc=0), got rc={rc} stderr={stderr!r}")

# ---------------------------------------------------------------- t3
print()
print("=== t3: plugin mode + declared path + marker → ALLOW ===")
with saved_state():
    write_mode("plugin")
    write_project_map({
        "schema_version": "1.0.0",
        "features": {
            TEST_FEATURE_NAME: {
                "paths": [TEST_PATH_GLOB],
                "feature_dir": "rabbit-project/features/" + TEST_FEATURE_NAME,
            }
        }
    })
    write_scope_active(TEST_FEATURE_NAME)
    rc, stderr = run_guard(TEST_TARGET)
    if rc == 0:
        ok("declared path + scope-active marker → ALLOW")
    else:
        fail_t(f"expected ALLOW (rc=0), got rc={rc} stderr={stderr!r}")

# ---------------------------------------------------------------- t4
print()
print("=== t4: plugin mode + declared path + NO marker → DENY ===")
with saved_state():
    write_mode("plugin")
    write_project_map({
        "schema_version": "1.0.0",
        "features": {
            TEST_FEATURE_NAME: {
                "paths": [TEST_PATH_GLOB],
                "feature_dir": "rabbit-project/features/" + TEST_FEATURE_NAME,
            }
        }
    })
    rc, stderr = run_guard(TEST_TARGET)
    if rc != 2:
        fail_t(f"expected DENY (rc=2), got rc={rc} stderr={stderr!r}")
    else:
        ok("declared path + no marker → DENY (exit 2)")
        for needle in ("DENY", "SESSION OVERRIDE", "ONE-TIME OVERRIDE",
                       "rabbit-feature-touch", TEST_FEATURE_NAME):
            if needle in stderr:
                ok(f"DENY message contains {needle!r}")
            else:
                fail_t(f"DENY message missing {needle!r}: {stderr!r}")

# ---------------------------------------------------------------- t5
print()
print("=== t5: plugin mode + .rabbit/.claude/** edit → DENY always ===")
with saved_state():
    write_mode("plugin")
    target = os.path.join(REPO_ROOT, ".rabbit", ".claude", "__test_evil__.py")
    rc, stderr = run_guard(target)
    if rc == 2 and "DENY" in stderr:
        ok("plugin mode rejects edits to .rabbit/.claude/**")
    else:
        fail_t(f"expected DENY (rc=2), got rc={rc} stderr={stderr!r}")

    target2 = os.path.join(REPO_ROOT, ".rabbit", "rabbit-project", "__test_evil__.json")
    rc2, stderr2 = run_guard(target2)
    if rc2 == 2 and "DENY" in stderr2:
        ok("plugin mode rejects edits to .rabbit/rabbit-project/**")
    else:
        fail_t(f"expected DENY (rc=2), got rc={rc2} stderr={stderr2!r}")

    target_carve = os.path.join(REPO_ROOT, ".rabbit", "CLAUDE.md")
    rc3, stderr3 = run_guard(target_carve)
    if rc3 == 0:
        ok("plugin mode allows carve-out .rabbit/CLAUDE.md")
    else:
        fail_t(f"expected ALLOW carve-out, got rc={rc3} stderr={stderr3!r}")

# ---------------------------------------------------------------- t6
print()
print("=== t6: bypass-once marker present → ALLOW + marker deleted ===")
with saved_state():
    write_mode("plugin")
    write_bypass_once()
    target = os.path.join(REPO_ROOT, ".rabbit", ".claude", "__test_evil__.py")
    rc, stderr = run_guard(target)
    if rc == 0:
        ok("bypass-once → ALLOW for normally-denied target")
    else:
        fail_t(f"expected ALLOW (rc=0), got rc={rc} stderr={stderr!r}")
    if not os.path.exists(BYPASS_FILE):
        ok("bypass-once marker deleted after consume")
    else:
        fail_t("bypass-once marker still present after consume")

# ---------------------------------------------------------------- t7
print()
print("=== t7: bypass-once consume-before-evaluate (marker always deleted) ===")
with saved_state():
    write_mode("plugin")
    write_bypass_once()
    target = os.path.join(REPO_ROOT, ".rabbit", ".claude", "__test_evil__.py")
    rc, _ = run_guard(target)
    if rc == 0:
        ok("bypass-once causes ALLOW")
    else:
        fail_t(f"expected ALLOW (rc=0), got rc={rc}")
    if not os.path.exists(BYPASS_FILE):
        ok("bypass-once marker consumed (deleted) regardless of outcome")
    else:
        fail_t("bypass-once marker not consumed — would leave persistent bypass")
    # After consumption, the next invocation must DENY (no lingering bypass).
    rc2, stderr2 = run_guard(target)
    if rc2 == 2:
        ok("second invocation with no marker correctly DENIES")
    else:
        fail_t(f"expected DENY after consume, got rc={rc2} stderr={stderr2!r}")

# ---------------------------------------------------------------- t8
print()
print("=== t8: scope-bypass-once path is on the static allowlist ===")
with saved_state():
    write_mode("plugin")
    # Creating the bypass marker itself in plugin mode must be allowed —
    # otherwise the user cannot enable the bypass via `touch`.
    target = BYPASS_FILE
    rc, stderr = run_guard(target)
    if rc == 0:
        ok("scope-bypass-once path itself is allowlisted")
    else:
        fail_t(f"expected ALLOW (rc=0), got rc={rc} stderr={stderr!r}")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
