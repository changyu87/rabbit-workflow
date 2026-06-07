#!/usr/bin/env python3
"""Inv 52 — `abort` releases the scope-active marker, mode-aware.

Scenarios:
  (A) Standalone (no .rabbit/.runtime/mode or content != 'plugin'):
      marker at <RABBIT_ROOT>/.rabbit-scope-active-<feature> is removed.
  (B) Plugin (.rabbit/.runtime/mode == 'plugin'):
      marker at <RABBIT_ROOT>/.rabbit/.runtime/scope-active-<feature>
      is removed.
  (C) Idempotent no-op: abort succeeds even when no marker exists.

The dual-mode path resolution matches Inv 12 / dispatch-tdd-subagent.py
_scope_marker_path().
"""
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TDD_STEP = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")

sys.path.insert(0, SCRIPT_DIR)
from state_machine_helpers import make_feature_dir  # noqa: E402

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def run(rabbit_root, *args):
    env = os.environ.copy()
    env["RABBIT_ROOT"] = rabbit_root
    return subprocess.run(
        ["python3", TDD_STEP] + list(args),
        capture_output=True, text=True, env=env,
    )


# Scenario A: standalone — marker at <rabbit_root>/.rabbit-scope-active-<feat>.
def t_standalone_marker_removed():
    with tempfile.TemporaryDirectory() as tmp:
        feat = "feata"
        feat_dir = os.path.join(tmp, feat)
        make_feature_dir(feat_dir, feat, "test-red")
        marker = os.path.join(tmp, f".rabbit-scope-active-{feat}")
        with open(marker, "w") as f:
            f.write("")
        res = run(tmp, "abort", feat_dir, "--reason", "blocked-by-#329")
        if res.returncode != 0:
            ko(f"standalone: abort rc={res.returncode} stderr={res.stderr!r}")
            return
        if not os.path.exists(marker):
            ok("Inv 52: standalone marker removed by abort")
        else:
            ko(f"Inv 52: standalone marker still present at {marker}")


# Scenario B: plugin — marker at <rabbit_root>/.rabbit/.runtime/scope-active-<feat>.
def t_plugin_marker_removed():
    with tempfile.TemporaryDirectory() as tmp:
        feat = "featb"
        feat_dir = os.path.join(tmp, feat)
        make_feature_dir(feat_dir, feat, "impl")
        runtime_dir = os.path.join(tmp, ".rabbit", ".runtime")
        os.makedirs(runtime_dir)
        with open(os.path.join(runtime_dir, "mode"), "w") as f:
            f.write("plugin\n")
        marker = os.path.join(runtime_dir, f"scope-active-{feat}")
        with open(marker, "w") as f:
            f.write("")
        res = run(tmp, "abort", feat_dir, "--reason", "discovered-blocker")
        if res.returncode != 0:
            ko(f"plugin: abort rc={res.returncode} stderr={res.stderr!r}")
            return
        if not os.path.exists(marker):
            ok("Inv 52: plugin marker removed by abort")
        else:
            ko(f"Inv 52: plugin marker still present at {marker}")
        # Standalone-form marker MUST NOT be created by accident.
        bad = os.path.join(tmp, f".rabbit-scope-active-{feat}")
        if not os.path.exists(bad):
            ok("Inv 52: plugin mode did NOT touch standalone-form marker")
        else:
            ko(f"Inv 52: plugin mode incorrectly touched {bad}")


# Scenario C: idempotent — no marker present, abort still succeeds.
def t_idempotent_no_marker():
    with tempfile.TemporaryDirectory() as tmp:
        feat = "featc"
        feat_dir = os.path.join(tmp, feat)
        make_feature_dir(feat_dir, feat, "sync-deployed")
        # No marker created.
        res = run(tmp, "abort", feat_dir, "--reason", "blocked-by-#329")
        if res.returncode == 0:
            ok("Inv 52: abort is idempotent when no marker exists (rc=0)")
        else:
            ko(f"Inv 52: idempotent abort failed rc={res.returncode} "
               f"stderr={res.stderr!r}")


t_standalone_marker_removed()
t_plugin_marker_removed()
t_idempotent_no_marker()

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
