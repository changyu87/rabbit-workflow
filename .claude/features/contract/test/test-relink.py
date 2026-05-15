#!/usr/bin/env python3
# test-relink.py — verify relink.sh creates symlinks from surface declarations.

import os
import sys
import subprocess
import tempfile
import shutil
import json

SCRIPTS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../scripts"))
RELINK = os.path.join(SCRIPTS_DIR, "relink.sh")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global FAIL
    print(f"  FAIL {msg}", file=sys.stderr)
    FAIL = 1


# ── setup: temp features dir with one feature ─────────────────────────────────
TMPDIR = tempfile.mkdtemp()


def cleanup():
    shutil.rmtree(TMPDIR, ignore_errors=True)


try:
    FEATURES = os.path.join(TMPDIR, "features")
    REPO = os.path.join(TMPDIR, "repo")
    os.makedirs(os.path.join(FEATURES, "myfeat/hooks"), exist_ok=True)
    os.makedirs(os.path.join(REPO, ".claude/hooks"), exist_ok=True)

    # Create a real file in the feature dir (the canonical source)
    hook_src = os.path.join(FEATURES, "myfeat/hooks/my-hook.sh")
    with open(hook_src, "w") as f:
        f.write("#!/bin/bash\n")
    os.chmod(hook_src, 0o755)

    # Create a registry.json
    registry = {
        "schema_version": "1.0.0",
        "owner": "test",
        "features": {
            "myfeat": {"name": "myfeat", "version": "1.0.0", "path": "features/myfeat"}
        }
    }
    with open(os.path.join(FEATURES, "registry.json"), "w") as f:
        json.dump(registry, f, indent=2)

    # Create feature.json with a surface hook entry
    feature_data = {
        "name": "myfeat",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "test feature",
        "surface": {
            "hooks": [".claude/hooks/my-hook.sh"],
            "commands": [],
            "agents": [],
            "skills": []
        }
    }
    with open(os.path.join(FEATURES, "myfeat/feature.json"), "w") as f:
        json.dump(feature_data, f, indent=2)

    # ── t1: relink exits 0 ────────────────────────────────────────────────────────
    r1 = subprocess.run(["bash", RELINK, FEATURES, REPO], capture_output=True)
    if r1.returncode == 0:
        ok("t1: relink exits 0")
    else:
        fail("t1: relink exited non-zero")

    # ── t2: symlink was created at surface path ───────────────────────────────────
    LINK = os.path.join(REPO, ".claude/hooks/my-hook.sh")
    if os.path.islink(LINK):
        ok("t2: symlink exists at surface path")
    else:
        fail(f"t2: symlink missing at {LINK}")

    # ── t3: symlink points to correct target ─────────────────────────────────────
    EXPECTED = os.path.join(FEATURES, "myfeat/hooks/my-hook.sh")
    ACTUAL = os.readlink(LINK) if os.path.islink(LINK) else ""
    if ACTUAL == EXPECTED:
        ok("t3: symlink target is correct")
    else:
        fail(f"t3: symlink target '{ACTUAL}' != '{EXPECTED}'")

    # ── t4: idempotent — second run exits 0 and skips (no error) ─────────────────
    r4 = subprocess.run(["bash", RELINK, FEATURES, REPO], capture_output=True)
    if r4.returncode == 0:
        ok("t4: second run (idempotent) exits 0")
    else:
        fail("t4: second run exited non-zero")

    # ── t5: existing regular file is skipped (not overwritten) ───────────────────
    TMPDIR2 = tempfile.mkdtemp()
    try:
        FEATURES2 = os.path.join(TMPDIR2, "features")
        REPO2 = os.path.join(TMPDIR2, "repo")
        os.makedirs(os.path.join(FEATURES2, "feat2"), exist_ok=True)
        os.makedirs(os.path.join(REPO2, ".claude/hooks"), exist_ok=True)

        hook2_src = os.path.join(FEATURES2, "feat2/my-hook.sh")
        with open(hook2_src, "w") as f:
            f.write("#!/bin/bash\n")
        os.chmod(hook2_src, 0o755)

        # Pre-existing regular file at surface path
        existing = os.path.join(REPO2, ".claude/hooks/my-hook.sh")
        with open(existing, "w") as f:
            f.write("original content\n")

        reg2 = {"schema_version": "1.0.0", "owner": "test", "features": {"feat2": {"name": "feat2", "version": "1.0.0", "path": "features/feat2"}}}
        with open(os.path.join(FEATURES2, "registry.json"), "w") as f:
            json.dump(reg2, f)

        fj2 = {"name": "feat2", "version": "1.0.0", "owner": "test", "tdd_state": "test-green", "summary": "t", "surface": {"hooks": [".claude/hooks/my-hook.sh"], "commands": [], "agents": [], "skills": []}}
        with open(os.path.join(FEATURES2, "feat2/feature.json"), "w") as f:
            json.dump(fj2, f)

        subprocess.run(["bash", RELINK, FEATURES2, REPO2], capture_output=True)
        hook2_path = os.path.join(REPO2, ".claude/hooks/my-hook.sh")
        if os.path.isfile(hook2_path) and not os.path.islink(hook2_path):
            ok("t5: regular file at surface path was not overwritten")
        else:
            fail("t5: regular file was overwritten or converted to symlink")
    finally:
        shutil.rmtree(TMPDIR2, ignore_errors=True)

    # ── t6: surface.root[] creates repo-root symlinks via artifacts/ ──────────────
    TMPDIR3 = tempfile.mkdtemp()
    try:
        FEATURES3 = os.path.join(TMPDIR3, "features")
        REPO3 = os.path.join(TMPDIR3, "repo")
        os.makedirs(os.path.join(FEATURES3, "rootfeat/artifacts"), exist_ok=True)
        os.makedirs(REPO3, exist_ok=True)

        install_src = os.path.join(FEATURES3, "rootfeat/artifacts/myinstall.sh")
        with open(install_src, "w") as f:
            f.write("#!/bin/bash\n")
        os.chmod(install_src, 0o755)

        reg3 = {"schema_version": "1.0.0", "owner": "test", "features": {"rootfeat": {"name": "rootfeat", "version": "1.0.0", "path": "features/rootfeat"}}}
        with open(os.path.join(FEATURES3, "registry.json"), "w") as f:
            json.dump(reg3, f)

        fj3 = {"name": "rootfeat", "version": "1.0.0", "owner": "test", "tdd_state": "test-green", "summary": "t", "surface": {"hooks": [], "commands": [], "agents": [], "skills": [], "root": ["myinstall.sh"]}}
        with open(os.path.join(FEATURES3, "rootfeat/feature.json"), "w") as f:
            json.dump(fj3, f)

        subprocess.run(["bash", RELINK, FEATURES3, REPO3], capture_output=True)
        ROOT_LINK = os.path.join(REPO3, "myinstall.sh")
        if os.path.islink(ROOT_LINK):
            ok("t6: root surface entry creates symlink at repo root")
        else:
            fail(f"t6: root symlink missing at {ROOT_LINK}")
    finally:
        shutil.rmtree(TMPDIR3, ignore_errors=True)

finally:
    cleanup()

# ── result ────────────────────────────────────────────────────────────────────
if FAIL != 0:
    print("test-relink: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-relink: all tests passed.")
