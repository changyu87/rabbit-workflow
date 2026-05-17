#!/usr/bin/env python3
"""Tests for RABBIT-CAGE-23: rename rbt- prefix → rabbit- prefix."""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
REFRESH_SH = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/refresh.py")
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")
SETTINGS_JSON = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/settings.json")
RABBIT_REFRESH_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/commands/rabbit-refresh.md")
WORKSPACE_TREE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/workspace-tree.py")
RABBIT_CONFIG_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/commands/rabbit-config.md")
RABBIT_CONFIG_PY = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py")

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


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


print("test-RABBIT-CAGE-23-rename-rbt-prefix.py")
print()

# t1
print("=== t1: refresh.py uses .rabbit-prompt-counter (not .rbt-prompt-counter) ===")
refresh = read(REFRESH_SH)
if ".rabbit-prompt-counter" in refresh:
    ok("refresh.py references .rabbit-prompt-counter")
else:
    fail_t("refresh.py does NOT reference .rabbit-prompt-counter")
if ".rbt-prompt-counter" in refresh:
    fail_t("refresh.py still references old .rbt-prompt-counter")
else:
    ok("refresh.py does NOT reference old .rbt-prompt-counter")

# t2
print("=== t2: refresh.py uses RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY) ===")
if "RABBIT_REFRESH_EVERY" in refresh:
    ok("refresh.py references RABBIT_REFRESH_EVERY")
else:
    fail_t("refresh.py does NOT reference RABBIT_REFRESH_EVERY")
if "RBT_REFRESH_EVERY" in refresh:
    fail_t("refresh.py still references old RBT_REFRESH_EVERY")
else:
    ok("refresh.py does NOT reference old RBT_REFRESH_EVERY")

# t3
print("=== t3: sync-check.py uses .rabbit-sync-counter (not .rbt-sync-counter) ===")
sync = read(SYNC_CHECK)
if ".rabbit-sync-counter" in sync:
    ok("sync-check.py references .rabbit-sync-counter")
else:
    fail_t("sync-check.py does NOT reference .rabbit-sync-counter")
if ".rbt-sync-counter" in sync:
    fail_t("sync-check.py still references old .rbt-sync-counter")
else:
    ok("sync-check.py does NOT reference old .rbt-sync-counter")

# t4
print("=== t4: sync-check.py uses RABBIT_SYNC_EVERY (not RBT_SYNC_EVERY) ===")
if "RABBIT_SYNC_EVERY" in sync:
    ok("sync-check.py references RABBIT_SYNC_EVERY")
else:
    fail_t("sync-check.py does NOT reference RABBIT_SYNC_EVERY")
if "RBT_SYNC_EVERY" in sync:
    fail_t("sync-check.py still references old RBT_SYNC_EVERY")
else:
    ok("sync-check.py does NOT reference old RBT_SYNC_EVERY")

# t5
print("=== t5: sync-check.py uses .rabbit-prompt-counter on first-run/drift paths ===")
if ".rabbit-prompt-counter" in sync:
    ok("sync-check.py references .rabbit-prompt-counter")
else:
    fail_t("sync-check.py does NOT reference .rabbit-prompt-counter")
if ".rbt-prompt-counter" in sync:
    fail_t("sync-check.py still references old .rbt-prompt-counter")
else:
    ok("sync-check.py does NOT reference old .rbt-prompt-counter")

# t6
print("=== t6: sync-check.py uses RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY) ===")
if "RABBIT_REFRESH_EVERY" in sync:
    ok("sync-check.py references RABBIT_REFRESH_EVERY")
else:
    fail_t("sync-check.py does NOT reference RABBIT_REFRESH_EVERY")
if "RBT_REFRESH_EVERY" in sync:
    fail_t("sync-check.py still references old RBT_REFRESH_EVERY")
else:
    ok("sync-check.py does NOT reference old RBT_REFRESH_EVERY")

# t7
print("=== t7: settings.json declares RABBIT_REFRESH_EVERY ===")
try:
    with open(SETTINGS_JSON) as f:
        settings = json.load(f)
    env = settings.get("env", {})
    if "RABBIT_REFRESH_EVERY" in env:
        ok("settings.json has RABBIT_REFRESH_EVERY in env")
    else:
        fail_t("settings.json does NOT have RABBIT_REFRESH_EVERY in env")
    if "RBT_REFRESH_EVERY" not in env:
        ok("settings.json does NOT have old RBT_REFRESH_EVERY in env")
    else:
        fail_t("settings.json still has old RBT_REFRESH_EVERY in env")
except Exception:
    fail_t("settings.json could not be loaded")

# t8
print("=== t8: settings.json SessionStart resets .rabbit-prompt-counter ===")
settings_content = read(SETTINGS_JSON)
if ".rabbit-prompt-counter" in settings_content:
    ok("settings.json references .rabbit-prompt-counter")
else:
    fail_t("settings.json does NOT reference .rabbit-prompt-counter")
if ".rbt-prompt-counter" in settings_content:
    fail_t("settings.json still references old .rbt-prompt-counter")
else:
    ok("settings.json does NOT reference old .rbt-prompt-counter")

# t9
print("=== t9: rabbit-refresh.md resets .rabbit-prompt-counter ===")
rrmd = read(RABBIT_REFRESH_MD)
if ".rabbit-prompt-counter" in rrmd:
    ok("rabbit-refresh.md references .rabbit-prompt-counter")
else:
    fail_t("rabbit-refresh.md does NOT reference .rabbit-prompt-counter")
if ".rbt-prompt-counter" in rrmd:
    fail_t("rabbit-refresh.md still references old .rbt-prompt-counter")
else:
    ok("rabbit-refresh.md does NOT reference old .rbt-prompt-counter")

# t10
print("=== t10: workspace-tree.py excludes .rabbit-prompt-counter ===")
wt = read(WORKSPACE_TREE)
if ".rabbit-prompt-counter" in wt:
    ok("workspace-tree.py references .rabbit-prompt-counter")
else:
    fail_t("workspace-tree.py does NOT reference .rabbit-prompt-counter")
if ".rbt-prompt-counter" in wt:
    fail_t("workspace-tree.py still references old .rbt-prompt-counter")
else:
    ok("workspace-tree.py does NOT reference old .rbt-prompt-counter")

# t11
# Inv 25 (updated): rabbit-config.md is a shim with no inline Python. The
# RABBIT_REFRESH_EVERY reference now lives in skills/rabbit-config/scripts/rabbit-config.py.
print("=== t11: rabbit-config.py uses RABBIT_REFRESH_EVERY ===")
rc = read(RABBIT_CONFIG_PY)
if "RABBIT_REFRESH_EVERY" in rc:
    ok("rabbit-config.py references RABBIT_REFRESH_EVERY")
else:
    fail_t("rabbit-config.py does NOT reference RABBIT_REFRESH_EVERY")
if "RBT_REFRESH_EVERY" in rc:
    fail_t("rabbit-config.py still references old RBT_REFRESH_EVERY")
else:
    ok("rabbit-config.py does NOT reference old RBT_REFRESH_EVERY")

# t12
print("=== t12: deployed refresh.py uses new names ===")
deployed_refresh = os.path.join(REPO_ROOT, ".claude/hooks/refresh.py")
if os.path.isfile(deployed_refresh):
    dr = read(deployed_refresh)
    if ".rbt-prompt-counter" in dr or "RBT_REFRESH_EVERY" in dr:
        fail_t("deployed refresh.py still references old rbt- names")
    else:
        ok("deployed refresh.py does NOT reference old rbt- names")
else:
    ok("deployed refresh.py not present (symlink or absent — skipping)")

# t13
print("=== t13: deployed sync-check.py uses new names ===")
deployed_sync = os.path.join(REPO_ROOT, ".claude/hooks/sync-check.py")
if os.path.isfile(deployed_sync):
    ds = read(deployed_sync)
    if any(x in ds for x in (".rbt-sync-counter", ".rbt-prompt-counter", "RBT_SYNC_EVERY", "RBT_REFRESH_EVERY")):
        fail_t("deployed sync-check.py still references old rbt- names")
    else:
        ok("deployed sync-check.py does NOT reference old rbt- names")
else:
    ok("deployed sync-check.py not present (symlink or absent — skipping)")

# t14
print("=== t14: deployed settings.json uses new names ===")
deployed_settings = os.path.join(REPO_ROOT, ".claude/settings.json")
if os.path.islink(deployed_settings):
    deployed_settings_real = os.path.realpath(deployed_settings)
else:
    deployed_settings_real = deployed_settings

if os.path.isfile(deployed_settings_real):
    dsj = read(deployed_settings_real)
    if "RBT_REFRESH_EVERY" in dsj or ".rbt-prompt-counter" in dsj:
        fail_t("deployed settings.json still references old rbt- names")
    else:
        ok("deployed settings.json does NOT reference old rbt- names")
else:
    ok("deployed settings.json not present — skipping")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
