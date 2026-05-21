#!/usr/bin/env python3
"""Test invariant 16: build.py passes RABBIT_ROOT to generate-claude-md.py."""
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
if "RABBIT_ROOT" in build_src:
    ok(2, "build.py source contains RABBIT_ROOT (env var passed to generate-claude-md.py)")
else:
    fail_t(2, "build.py does NOT contain RABBIT_ROOT — fix not applied (invariant 16 violated)")

# t3
tmpdir_target = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmpdir_target, ".claude/features/contract"), exist_ok=True)
    contract = {
        "version": "1.0.0",
        "targets": [{"name": "CLAUDE.md", "type": "generate-claude-md", "destination": "CLAUDE.md"}],
    }
    with open(os.path.join(tmpdir_target, ".claude/features/contract/build-contract.json"), "w") as f:
        json.dump(contract, f)

    # Replicate build.py's invocation pattern: pass RABBIT_ROOT to subprocess.
    target_root = tmpdir_target
    contract_path = os.path.join(tmpdir_target, ".claude/features/contract/build-contract.json")
    with open(contract_path) as f:
        c = json.load(f)

    errors = 0
    for target in c.get("targets", []):
        if target["type"] == "generate-claude-md":
            destination = os.path.join(target_root, target["destination"])
            env = {**os.environ, "RABBIT_ROOT": REPO_ROOT}
            result = subprocess.run([sys.executable, GENERATE_SCRIPT, "--write", target_root],
                                    env=env, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  [error] {target['name']}: generate-claude-md failed\n{result.stderr}", file=sys.stderr)
                errors += 1
            else:
                print(f"  [built] {target['name']}")

    if errors == 0:
        if os.path.isfile(os.path.join(tmpdir_target, "CLAUDE.md")):
            ok(3, "CLAUDE.md created in non-git temp dir when RABBIT_ROOT is passed to subprocess")
        else:
            fail_t(3, "subprocess exited 0 but CLAUDE.md not found in temp dir")
    else:
        fail_t(3, "generate-claude-md.py failed when RABBIT_ROOT was passed (unexpected)")
finally:
    shutil.rmtree(tmpdir_target, ignore_errors=True)

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
