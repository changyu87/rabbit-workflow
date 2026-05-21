#!/usr/bin/env python3
"""Drift oracle for workspace-generated artifacts."""
import filecmp
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
BUILD_SH = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/build.py")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-generated-surface.py")

# t1
if os.path.isfile(BUILD_SH) and os.access(BUILD_SH, os.X_OK):
    ok(1, "build.py exists and is executable")
else:
    fail_t(1, f"build.py not found or not executable at {BUILD_SH}")

# t2: at least 5 active feature publish.json manifests exist
features_dir = os.path.join(REPO_ROOT, ".claude/features")
publish_count = 0
for d in os.listdir(features_dir):
    fj = os.path.join(features_dir, d, "feature.json")
    pj = os.path.join(features_dir, d, "publish.json")
    if not os.path.isfile(fj) or not os.path.isfile(pj):
        continue
    try:
        if json.load(open(fj)).get("status") != "retired":
            publish_count += 1
    except Exception:
        pass
if publish_count >= 5:
    ok(2, f"found {publish_count} active feature publish.json manifests")
else:
    fail_t(2, f"expected >= 5 active feature publish.json files, found {publish_count}")

if fail_n > 0:
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# t3+: all check_on_stop=true targets in all feature publish.json files are in sync
t = 3
for feature_dir_name in sorted(os.listdir(features_dir)):
    feature_dir = os.path.join(features_dir, feature_dir_name)
    fj = os.path.join(feature_dir, "feature.json")
    pj = os.path.join(feature_dir, "publish.json")
    if not os.path.isfile(fj) or not os.path.isfile(pj):
        continue
    try:
        if json.load(open(fj)).get("status") == "retired":
            continue
        manifest = json.load(open(pj))
    except Exception:
        continue
    for target in manifest.get("targets", []):
        if not (target.get("check_on_stop") and target["type"] == "copy-file"):
            continue
        name = target["name"]
        src_abs = os.path.join(feature_dir, target["source"])
        dst_abs = os.path.join(REPO_ROOT, target["destination"])
        if not os.path.isfile(src_abs):
            fail_t(t, f"{name}: source missing: {src_abs}")
            t += 1
            continue
        if not os.path.isfile(dst_abs):
            fail_t(t, f"{name}: destination missing: {dst_abs}")
        elif not filecmp.cmp(src_abs, dst_abs, shallow=False):
            fail_t(t, f"{name}: source and destination differ")
        else:
            ok(t, f"{name}: source and destination in sync")
        t += 1

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
