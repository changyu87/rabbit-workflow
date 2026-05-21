#!/usr/bin/env python3
"""Test invariant 16: build.py federated-discovery model."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
BUILD_SH = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/build.py")
GENERATE_SCRIPT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")

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


print("test-build-non-git-dir.py")

# t1
if os.path.isfile(BUILD_SH) and os.access(BUILD_SH, os.X_OK):
    ok(1, "build.py exists and is executable")
else:
    fail_t(1, "build.py missing or not executable")

# t2
with open(BUILD_SH) as f:
    build_src = f.read()
if "_discover_manifests" in build_src:
    ok(2, "build.py source contains _discover_manifests (federated discovery)")
else:
    fail_t(2, "build.py does NOT contain _discover_manifests — federated discovery missing")

# t3: build.py processes publish.json targets in a non-git dir when REPO_ROOT arg is given
tmpdir_target = tempfile.mkdtemp()
try:
    feature_dir = os.path.join(tmpdir_target, ".claude/features/fake-feature")
    os.makedirs(feature_dir, exist_ok=True)
    with open(os.path.join(feature_dir, "feature.json"), "w") as f:
        json.dump({"name": "fake-feature", "version": "1.0.0", "owner": "test",
                   "status": "active", "deprecation_criterion": "n/a"}, f)
    os.makedirs(os.path.join(feature_dir, "src"), exist_ok=True)
    with open(os.path.join(feature_dir, "src/hello.txt"), "w") as f:
        f.write("hello\n")
    publish = {
        "schema_version": "1.0.0", "feature": "fake-feature",
        "owner": "test", "deprecation_criterion": "n/a",
        "targets": [{"name": "hello.txt", "type": "copy-file",
                     "source": "src/hello.txt", "destination": "dst/hello.txt",
                     "check_on_stop": False}],
    }
    with open(os.path.join(feature_dir, "publish.json"), "w") as f:
        json.dump(publish, f)

    result = subprocess.run(
        [sys.executable, BUILD_SH, tmpdir_target],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and os.path.isfile(os.path.join(tmpdir_target, "dst/hello.txt")):
        ok(3, "build.py processes publish.json targets in non-git dir when REPO_ROOT arg given")
    else:
        fail_t(3, f"build.py failed in non-git dir: rc={result.returncode} stderr={result.stderr!r}")
finally:
    shutil.rmtree(tmpdir_target, ignore_errors=True)

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
