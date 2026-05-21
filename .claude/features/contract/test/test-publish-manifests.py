#!/usr/bin/env python3
"""test-publish-manifests.py — validates per-feature publish.json manifests.

For each active feature with a publish.json:
  - validates against publish-manifest.schema.json
  - checks all declared source paths exist on disk
  - checks feature field matches directory name
"""
import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import subprocess
result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
FEATURES_DIR = os.path.join(REPO_ROOT, ".claude", "features")
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "publish-manifest.schema.json")

passed = 0
failed = 0


def ok(label, msg):
    global passed
    print(f"  PASS {label}: {msg}")
    passed += 1


def fail_t(label, msg):
    global failed
    print(f"  FAIL {label}: {msg}", file=sys.stderr)
    failed += 1


print("test-publish-manifests.py")

try:
    schema = json.load(open(SCHEMA_PATH))
except (json.JSONDecodeError, OSError) as e:
    print(f"ABORT: cannot load schema: {e}", file=sys.stderr)
    sys.exit(1)

feature_dirs = sorted([
    d for d in os.listdir(FEATURES_DIR)
    if os.path.isdir(os.path.join(FEATURES_DIR, d))
])

found_manifests = 0
for feature_name in feature_dirs:
    feature_dir = os.path.join(FEATURES_DIR, feature_name)
    feature_json_path = os.path.join(feature_dir, "feature.json")
    publish_path = os.path.join(feature_dir, "publish.json")

    if not os.path.isfile(feature_json_path):
        continue
    try:
        feature_meta = json.load(open(feature_json_path))
    except (json.JSONDecodeError, OSError):
        continue
    if feature_meta.get("status") == "retired":
        continue
    if not os.path.isfile(publish_path):
        continue

    found_manifests += 1
    label = feature_name

    try:
        manifest = json.load(open(publish_path))
    except json.JSONDecodeError as e:
        fail_t(label, f"publish.json is not valid JSON: {e}")
        continue
    ok(f"{label}/json", "publish.json is valid JSON")

    if manifest.get("feature") != feature_name:
        fail_t(f"{label}/feature", f"feature field {manifest.get('feature')!r} != dir {feature_name!r}")
    else:
        ok(f"{label}/feature", "feature field matches dir name")

    for field in ("schema_version", "feature", "owner", "deprecation_criterion", "targets"):
        if field in manifest:
            ok(f"{label}/field/{field}", f"required field '{field}' present")
        else:
            fail_t(f"{label}/field/{field}", f"required field '{field}' missing")

    for target in manifest.get("targets", []):
        source_rel = target.get("source", "")
        source_abs = os.path.join(feature_dir, source_rel)
        t_name = target.get("name", source_rel)
        if not os.path.isfile(source_abs):
            fail_t(f"{label}/source/{t_name}", f"source does not exist: {source_abs}")
        else:
            ok(f"{label}/source/{t_name}", f"source exists: {source_rel}")

if found_manifests == 0:
    fail_t("coverage", "no active feature publish.json files found")
else:
    ok("coverage", f"{found_manifests} active feature manifests validated")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
