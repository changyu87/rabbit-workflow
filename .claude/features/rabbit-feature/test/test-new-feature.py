#!/usr/bin/env python3
"""End-to-end tests for new-feature.py (relocated from rabbit-cage).

Locks the post-RABBIT-CAGE-BACKLOG-26 home of the scaffolder:
  - script lives at .claude/features/rabbit-feature/scripts/new-feature.py
  - script is executable
  - scaffolds test/run.py (Python-only stack), not test/run.sh
  - scaffolded feature.json carries template_version
  - scaffolded feature passes validate-feature.py immediately

These tests replace the equivalent rabbit-cage Inv 46 tests previously
hosted in rabbit-cage/test/test-RABBIT-CAGE-WAVE3-inv66-68.py — moved
when new-feature.py moved, so the tests sit with the code they cover
per Bounded Scope.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the scaffolder is rewritten or replaced by a
    native rabbit-feature subcommand.
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

NEW_FEATURE_PY = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-feature/scripts/new-feature.py"
)
VALIDATE_FEATURE_PY = os.path.join(
    REPO_ROOT, ".claude/features/contract/scripts/validate-feature.py"
)

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


print("test-new-feature.py")

# t1: script exists at the new path.
if os.path.isfile(NEW_FEATURE_PY):
    ok(1, "new-feature.py present at rabbit-feature/scripts/")
else:
    fail_t(1, f"new-feature.py missing at {NEW_FEATURE_PY}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# t2: script is executable.
if os.access(NEW_FEATURE_PY, os.X_OK):
    ok(2, "new-feature.py is executable")
else:
    fail_t(2, "new-feature.py is not executable")

# t3-t7: scaffold a feature and check the produced layout.
with tempfile.TemporaryDirectory(prefix="rf-new-feature-") as tmp:
    env = dict(os.environ)
    env["RABBIT_ROOT"] = REPO_ROOT
    res = subprocess.run(
        [sys.executable, NEW_FEATURE_PY, tmp, "demo-feature",
         "--owner", "rf-test", "--description", "demo"],
        env=env, capture_output=True, text=True,
    )
    if res.returncode != 0:
        fail_t(3, f"new-feature.py exited {res.returncode}; stderr={res.stderr!r}")
    else:
        ok(3, "new-feature.py scaffolds successfully")

    feature_dir = os.path.join(tmp, "demo-feature")
    run_py = os.path.join(feature_dir, "test", "run.py")
    run_sh = os.path.join(feature_dir, "test", "run.sh")

    # t4: test/run.py exists.
    if os.path.isfile(run_py):
        ok(4, "scaffold creates test/run.py")
    else:
        fail_t(4, "scaffold missing test/run.py")

    # t5: test/run.sh must NOT be created (Python-only stack).
    if not os.path.lexists(run_sh):
        ok(5, "scaffold does NOT create test/run.sh (Python-only)")
    else:
        fail_t(5, "scaffold creates test/run.sh (violates Python-only stack)")

    # t6: feature.json carries template_version.
    fjson = os.path.join(feature_dir, "feature.json")
    if os.path.isfile(fjson):
        try:
            with open(fjson) as f:
                data = json.load(f)
            if data.get("template_version"):
                ok(6, f"feature.json carries template_version={data['template_version']!r}")
            else:
                fail_t(6, "feature.json missing template_version")
        except Exception as e:
            fail_t(6, f"feature.json parse failure: {e}")
    else:
        fail_t(6, "feature.json was not scaffolded")

    # t7: validate-feature.py passes on the fresh scaffold.
    if os.path.isfile(VALIDATE_FEATURE_PY):
        vres = subprocess.run(
            [sys.executable, VALIDATE_FEATURE_PY, feature_dir],
            capture_output=True, text=True,
        )
        if vres.returncode == 0:
            ok(7, "scaffolded feature passes validate-feature.py immediately")
        else:
            fail_t(7, f"validate-feature.py rc={vres.returncode}; stderr={vres.stderr!r}")
    else:
        fail_t(7, f"validate-feature.py not found at {VALIDATE_FEATURE_PY}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
