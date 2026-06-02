#!/usr/bin/env python3
"""Inv 50, 51 — `tdd-step.py abort` subcommand shape and per-state
acceptance/rejection.

Inv 50: abort <feature_dir> --reason <code> subcommand exists; --reason
        is REQUIRED (exit 2 when omitted).
Inv 51: abort is accepted from {test-red, impl, sync-deployed} (exit 0)
        and rejected (exit 1) from {spec, spec-update, deprecated};
        deprecated rejection holds unconditionally (no --force override).
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

TMPROOT = tempfile.mkdtemp()

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


def run(*args):
    return subprocess.run(
        ["python3", TDD_STEP] + list(args),
        capture_output=True, text=True,
    )


# Inv 50 (a): abort subcommand must exist (not "unknown subcommand").
def t_subcommand_exists():
    d = os.path.join(TMPROOT, "exists")
    make_feature_dir(d, "exists", "test-red")
    res = run("abort", d, "--reason", "blocked-by-#329")
    if "unknown subcommand" in res.stderr:
        ko("Inv 50: abort subcommand missing (stderr says unknown)")
    else:
        ok("Inv 50: abort subcommand exists (not reported as unknown)")


# Inv 50 (b): --reason is required; missing => exit 2 (invocation error).
def t_reason_required_no_flag():
    d = os.path.join(TMPROOT, "reason_missing")
    make_feature_dir(d, "reason_missing", "test-red")
    res = run("abort", d)
    if res.returncode == 2:
        ok("Inv 50: abort without --reason exits 2")
    else:
        ko(f"Inv 50: abort without --reason rc={res.returncode}, "
           f"expected 2 (stderr={res.stderr!r})")


def t_reason_required_empty_value():
    d = os.path.join(TMPROOT, "reason_empty")
    make_feature_dir(d, "reason_empty", "test-red")
    res = run("abort", d, "--reason", "")
    if res.returncode == 2:
        ok("Inv 50: abort with empty --reason exits 2")
    else:
        ko(f"Inv 50: abort with empty --reason rc={res.returncode}, "
           f"expected 2 (stderr={res.stderr!r})")


# Inv 51 (acceptance): test-red / impl / sync-deployed are accepted.
def t_accept_from(state):
    d = os.path.join(TMPROOT, f"accept_{state}")
    make_feature_dir(d, f"accept_{state}", state)
    res = run("abort", d, "--reason", "discovered-blocker")
    if res.returncode == 0:
        ok(f"Inv 51: abort accepted from {state} (rc=0)")
    else:
        ko(f"Inv 51: abort from {state} rc={res.returncode}, "
           f"expected 0 (stderr={res.stderr!r})")


# Inv 51 (rejection): spec / spec-update / deprecated rejected with exit 1.
def t_reject_from(state):
    d = os.path.join(TMPROOT, f"reject_{state}")
    make_feature_dir(d, f"reject_{state}", state)
    res = run("abort", d, "--reason", "blocked-by-#329")
    if res.returncode == 1:
        ok(f"Inv 51: abort rejected from {state} (rc=1)")
    else:
        ko(f"Inv 51: abort from {state} rc={res.returncode}, "
           f"expected 1 (stderr={res.stderr!r})")


# Inv 51 (deprecated rejection holds even with --force).
def t_deprecated_force_still_rejected():
    d = os.path.join(TMPROOT, "reject_deprecated_force")
    make_feature_dir(d, "reject_deprecated_force", "deprecated")
    res = run("abort", d, "--reason", "blocked-by-#329", "--force")
    # --force is either silently ignored (still rc=1) or rejected as unknown
    # flag (rc=2); either outcome means deprecated is not aborted.
    if res.returncode != 0:
        ok(f"Inv 51: abort from deprecated rejected even with --force "
           f"(rc={res.returncode})")
    else:
        ko("Inv 51: abort from deprecated must reject even with --force")


t_subcommand_exists()
t_reason_required_no_flag()
t_reason_required_empty_value()
for s in ("test-red", "impl", "sync-deployed"):
    t_accept_from(s)
for s in ("spec", "spec-update", "deprecated"):
    t_reject_from(s)
t_deprecated_force_still_rejected()

print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
