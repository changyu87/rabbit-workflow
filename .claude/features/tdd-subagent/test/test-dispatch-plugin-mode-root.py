#!/usr/bin/env python3
"""Inv 47 — dispatch-tdd-subagent.py plugin-mode root resolution.

Three scenarios per spec Inv 47:
  A) Standalone: RABBIT_ROOT unset, dispatcher falls back to git rev-parse.
  B) Plugin (RABBIT_ROOT set): dispatcher uses RABBIT_ROOT verbatim and
     locates a user-project feature under <root>/rabbit-project/features/.
  C) Regression for #301/#302: plugin layout where host has .git/ but no
     .claude/ at host level; dispatcher MUST use RABBIT_ROOT (not fall
     back to git rev-parse to a non-existent <host>/.claude/...).
"""
import os
import shutil
import subprocess
import sys
import tempfile

from _helpers import DISPATCH_PY, FEATURE_DIR, REPO_ROOT, SPEC_PATH, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _populate_rabbit_root(root):
    """Copy the live contract/tdd-subagent feature trees into `root` so that
    find-feature.py + build-prompt.py + templates are all present. Mirrors
    the layout of a plugin install's <host>/.rabbit/ directory.
    """
    # Copy .claude/features/{contract,tdd-subagent,policy} verbatim.
    src_features = os.path.join(REPO_ROOT, ".claude", "features")
    dst_features = os.path.join(root, ".claude", "features")
    for feat in ("contract", "tdd-subagent", "policy"):
        src = os.path.join(src_features, feat)
        dst = os.path.join(dst_features, feat)
        if os.path.isdir(src):
            shutil.copytree(src, dst)


# ---------------------------------------------------------------------------
# Scenario A: standalone — RABBIT_ROOT unset, git rev-parse fallback.
# ---------------------------------------------------------------------------
# The live repo IS a standalone rabbit-self repo. Invoke dispatcher without
# RABBIT_ROOT and assert exit 0 (the dispatcher finds the tdd-subagent
# feature via git rev-parse fallback).
env = os.environ.copy()
env.pop("RABBIT_ROOT", None)
res = subprocess.run(
    [sys.executable, DISPATCH_PY, "--scope", "tdd-subagent", "--spec", SPEC_PATH],
    capture_output=True, text=True, env=env,
)
if res.returncode == 0 and res.stdout.strip():
    ok("scenario A: standalone (RABBIT_ROOT unset) → git rev-parse fallback succeeds")
else:
    ko(f"scenario A: expected rc=0, got rc={res.returncode}, stderr={res.stderr!r}")

# ---------------------------------------------------------------------------
# Scenario B: plugin mode — RABBIT_ROOT set, locates user-project feature.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    rabbit_root = os.path.join(tmp, ".rabbit")
    os.makedirs(rabbit_root)
    _populate_rabbit_root(rabbit_root)

    # Plugin-mode marker.
    _write(os.path.join(rabbit_root, ".runtime", "mode"), "plugin")

    # User-project feature with a real spec file.
    proj_feat_dir = os.path.join(rabbit_root, "rabbit-project", "features", "run-ingest")
    os.makedirs(proj_feat_dir)
    _write(os.path.join(proj_feat_dir, "feature.json"),
           '{"name": "run-ingest", "version": "0.1.0", "owner": "x", '
           '"summary": "x", "surface": {"hooks": [], "commands": [], '
           '"skills": []}, "tdd_state": "spec"}')
    proj_spec = os.path.join(proj_feat_dir, "docs", "spec", "spec.md")
    _write(proj_spec, "# run-ingest spec\n")

    env = os.environ.copy()
    env["RABBIT_ROOT"] = rabbit_root
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "run-ingest", "--spec", proj_spec],
        capture_output=True, text=True, env=env,
    )
    if res.returncode == 0 and "run-ingest" in res.stdout:
        ok("scenario B: plugin RABBIT_ROOT → locates user-project feature run-ingest")
    else:
        ko(f"scenario B: expected rc=0 + feature found, got rc={res.returncode}, "
           f"stderr={res.stderr!r}")

# ---------------------------------------------------------------------------
# Scenario C (regression #301/#302): plugin layout, host has .git/ but no
# .claude/. Dispatcher MUST use RABBIT_ROOT, not fall back to git rev-parse
# of the host (which would yield a stale <host>/.claude/... lookup).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    # Simulate a host project: .git/ at host top, but NO .claude/.
    os.makedirs(os.path.join(tmp, ".git"))
    rabbit_root = os.path.join(tmp, ".rabbit")
    os.makedirs(rabbit_root)
    _populate_rabbit_root(rabbit_root)
    _write(os.path.join(rabbit_root, ".runtime", "mode"), "plugin")

    proj_feat_dir = os.path.join(rabbit_root, "rabbit-project", "features", "run-ingest")
    os.makedirs(proj_feat_dir)
    _write(os.path.join(proj_feat_dir, "feature.json"),
           '{"name": "run-ingest", "version": "0.1.0", "owner": "x", '
           '"summary": "x", "surface": {"hooks": [], "commands": [], '
           '"skills": []}, "tdd_state": "spec"}')
    proj_spec = os.path.join(proj_feat_dir, "docs", "spec", "spec.md")
    _write(proj_spec, "# run-ingest spec\n")

    env = os.environ.copy()
    env["RABBIT_ROOT"] = rabbit_root
    # cwd is the host root — if the dispatcher git-rev-parse'd it would land
    # at <tmp>/ and then look for <tmp>/.claude/features/contract/scripts/
    # find-feature.py, which does NOT exist. Correct behavior: use RABBIT_ROOT.
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "run-ingest", "--spec", proj_spec],
        capture_output=True, text=True, env=env, cwd=tmp,
    )
    if res.returncode == 0 and "run-ingest" in res.stdout:
        ok("scenario C (#301/#302): plugin layout with host-level .git/ but no "
           ".claude/ — RABBIT_ROOT honored, no host fallback")
    else:
        ko(f"scenario C: expected rc=0, got rc={res.returncode}, "
           f"stderr={res.stderr!r}")


report(passed, failed)
