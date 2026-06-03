#!/usr/bin/env python3
"""Inv 12 (mode-aware amendment) — LOCK/UNLOCK scope-marker path is
mode-aware at prompt-assembly time.

Two scenarios mirror rabbit-cage Inv 17(b):

  A) Standalone (no `.rabbit/.runtime/mode` file present): assembled
     prompt's LOCK line ends with `.rabbit-scope-active-<feature>` (dashed
     standalone form, at repo-root) and contains NO `.rabbit/.runtime/
     scope-active-` form. UNLOCK mirrors.

  B) Plugin (`.rabbit/.runtime/mode == 'plugin'`): assembled prompt's
     LOCK line ends with `.rabbit/.runtime/scope-active-<feature>`
     (slash-separated `.runtime/scope-active-` form, NOT the dashed
     standalone form). UNLOCK mirrors.

Both scenarios run `dispatch-tdd-subagent.py` as a subprocess against a
tmpdir fixture populated with the live contract/tdd-subagent/policy
feature trees so the dispatcher's build-prompt subprocess can resolve
templates and slot declarations.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from _helpers import DISPATCH_PY, REPO_ROOT, SPEC_PATH, report

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
    """Copy contract/tdd-subagent/policy features into `root`."""
    src_features = os.path.join(REPO_ROOT, ".claude", "features")
    dst_features = os.path.join(root, ".claude", "features")
    for feat in ("contract", "tdd-subagent", "policy"):
        src = os.path.join(src_features, feat)
        dst = os.path.join(dst_features, feat)
        if os.path.isdir(src):
            shutil.copytree(src, dst)


def _make_project_feature(rabbit_root, feature_name):
    """Create a minimal user-project feature under rabbit-project/features/."""
    feat_dir = os.path.join(rabbit_root, "rabbit-project", "features", feature_name)
    os.makedirs(feat_dir)
    _write(os.path.join(feat_dir, "feature.json"),
           '{"name": "' + feature_name + '", "version": "0.1.0", '
           '"owner": "x", "summary": "x", '
           '"surface": {"hooks": [], "commands": [], "skills": []}, '
           '"tdd_state": "spec"}')
    spec = os.path.join(feat_dir, "docs", "spec", "spec.md")
    _write(spec, "# " + feature_name + " spec\n")
    return spec


def _extract_lock_body(prompt):
    m = re.search(r"STEP 1 — LOCK\n═+\n(.*?)\n═+\nSTEP 2", prompt, re.DOTALL)
    return m.group(1) if m else None


def _extract_unlock_body(prompt):
    m = re.search(r"STEP 8 — UNLOCK\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Scenario A: standalone — no .rabbit/.runtime/mode file.
#
# Use the live repo's own tdd-subagent feature (no `.rabbit/.runtime/mode`
# present in the repo root). Assembled prompt's LOCK/UNLOCK lines must
# reference the dashed standalone path form.
# ---------------------------------------------------------------------------
env = os.environ.copy()
env.pop("RABBIT_ROOT", None)

# Make sure the live repo is in standalone mode (mode file absent or
# contains 'standalone'). If the file says 'plugin', scenario A would
# legitimately produce the plugin-form output and the assertion would be
# wrong.
live_mode = os.path.join(REPO_ROOT, ".rabbit", ".runtime", "mode")
live_mode_value = ""
if os.path.isfile(live_mode):
    with open(live_mode) as _f:
        live_mode_value = _f.read().strip()
if live_mode_value == "plugin":
    ko(f"scenario A precondition: live repo {live_mode} is 'plugin'; "
       "cannot test standalone path here")
else:
    spec_path = SPEC_PATH
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "tdd-subagent",
         "--spec", spec_path],
        capture_output=True, text=True, env=env,
    )
    if res.returncode != 0:
        ko(f"scenario A: dispatch failed rc={res.returncode}: {res.stderr!r}")
    else:
        prompt = res.stdout
        lock_body = _extract_lock_body(prompt)
        unlock_body = _extract_unlock_body(prompt)
        if lock_body is None:
            ko("scenario A: LOCK section not isolated")
        else:
            # The literal touch line must reference the standalone form.
            # Inv 58: the marker path is repo-RELATIVE, so at repo-root it
            # is the bare `.rabbit-scope-active-tdd-subagent` (no leading
            # directory or slash).
            if re.search(r"touch\s+\.rabbit-scope-active-tdd-subagent\b",
                         lock_body):
                ok("scenario A: LOCK uses standalone relative path "
                   "(.rabbit-scope-active-tdd-subagent)")
            else:
                ko("scenario A: LOCK missing standalone-path touch")
            if ".rabbit/.runtime/scope-active-" not in lock_body:
                ok("scenario A: LOCK contains NO plugin path "
                   "(.rabbit/.runtime/scope-active-)")
            else:
                ko("scenario A: LOCK leaked plugin path "
                   "(.rabbit/.runtime/scope-active-)")
        if unlock_body is None:
            ko("scenario A: UNLOCK section not isolated")
        else:
            if re.search(r"rm -f\s+\.rabbit-scope-active-tdd-subagent\b",
                         unlock_body):
                ok("scenario A: UNLOCK uses standalone relative path "
                   "(.rabbit-scope-active-tdd-subagent)")
            else:
                ko("scenario A: UNLOCK missing standalone-path rm")
            if ".rabbit/.runtime/scope-active-" not in unlock_body:
                ok("scenario A: UNLOCK contains NO plugin path")
            else:
                ko("scenario A: UNLOCK leaked plugin path")


# ---------------------------------------------------------------------------
# Scenario B: plugin — `.rabbit/.runtime/mode == 'plugin'` at repo root.
#
# Populate a tmpdir with .rabbit/.claude/features/{contract,tdd-subagent,
# policy} and .rabbit/.runtime/mode='plugin'. Set RABBIT_ROOT to the
# rabbit-root (per Inv 47). Dispatch a user-project feature and assert
# LOCK/UNLOCK lines reference the plugin path form.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    rabbit_root = os.path.join(tmp, ".rabbit")
    os.makedirs(rabbit_root)
    _populate_rabbit_root(rabbit_root)
    _write(os.path.join(rabbit_root, ".runtime", "mode"), "plugin")
    proj_spec = _make_project_feature(rabbit_root, "run-ingest")

    env = os.environ.copy()
    env["RABBIT_ROOT"] = rabbit_root
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "run-ingest",
         "--spec", proj_spec],
        capture_output=True, text=True, env=env,
    )
    if res.returncode != 0:
        ko(f"scenario B: dispatch failed rc={res.returncode}: {res.stderr!r}")
    else:
        prompt = res.stdout
        lock_body = _extract_lock_body(prompt)
        unlock_body = _extract_unlock_body(prompt)
        if lock_body is None:
            ko("scenario B: LOCK section not isolated")
        else:
            # The literal touch line must reference the plugin form. Inv 58:
            # the marker is repo-RELATIVE; in plugin mode repo_root IS the
            # rabbit-root, so the plugin marker
            # `<rabbit_root>/.runtime/scope-active-<feature>` relativizes to
            # `.runtime/scope-active-<feature>` (no leading `.rabbit/` and no
            # absolute prefix).
            if re.search(r"touch\s+\.runtime/scope-active-run-ingest\b",
                         lock_body):
                ok("scenario B: LOCK uses plugin relative path "
                   "(.runtime/scope-active-run-ingest)")
            else:
                ko("scenario B: LOCK missing plugin-path touch")
            # Plugin-mode prompt must NOT contain the dashed standalone form.
            if not re.search(r"\.rabbit-scope-active-run-ingest\b", lock_body):
                ok("scenario B: LOCK contains NO standalone path "
                   "(.rabbit-scope-active-run-ingest)")
            else:
                ko("scenario B: LOCK leaked standalone path "
                   "(.rabbit-scope-active-run-ingest)")
        if unlock_body is None:
            ko("scenario B: UNLOCK section not isolated")
        else:
            if re.search(r"rm -f\s+\.runtime/scope-active-run-ingest\b",
                         unlock_body):
                ok("scenario B: UNLOCK uses plugin relative path "
                   "(.runtime/scope-active-run-ingest)")
            else:
                ko("scenario B: UNLOCK missing plugin-path rm")
            if not re.search(r"\.rabbit-scope-active-run-ingest\b", unlock_body):
                ok("scenario B: UNLOCK contains NO standalone path")
            else:
                ko("scenario B: UNLOCK leaked standalone path")


report(passed, failed)
