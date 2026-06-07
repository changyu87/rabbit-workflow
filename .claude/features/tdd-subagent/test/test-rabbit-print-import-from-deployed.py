#!/usr/bin/env python3
"""Inv 55 — tdd-step.py resolves the contract rabbit_print module from BOTH
its source and its DEPLOYED location.

Issue #561: the rabbit_print import computed the contract-scripts path with a
fixed `_Path(__file__).parents[2] / "contract" / "scripts"`. That offset only
holds at the SOURCE location (.claude/features/tdd-subagent/scripts/, whose
parents[2] is .claude/features/). At the DEPLOYED location
(.claude/agents/tdd-subagent/scripts/) parents[2] is .claude/, so the path
became .claude/contract/scripts — which does not exist — and the import raised
ModuleNotFoundError: No module named 'rabbit_print', even on --help, making
the scripted TDD-step driver unusable from the deployed copy.

Fix: resolve the repo root (cwd-based git toplevel, consistent with the #583
_repo_root fix, with a robust upward fallback) and build the contract-scripts
path as <repo_root>/.claude/features/contract/scripts, so the import works
from any copy depth.

This is an END-TO-END test: it stages a real git repo containing both the
SOURCE layout (.claude/features/tdd-subagent/scripts/) and the DEPLOYED layout
(.claude/agents/tdd-subagent/scripts/), plus the real contract rabbit_print
module under .claude/features/contract/scripts/. It then runs `tdd-step.py
--help` in a subprocess from each copy and asserts both load the module (no
ModuleNotFoundError, exit 0).
"""
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REPO_ROOT = os.path.abspath(os.path.join(FEATURE_DIR, "..", "..", ".."))
TDD_STEP = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")
RABBIT_PRINT = os.path.join(
    REPO_ROOT, ".claude", "features", "contract", "scripts", "rabbit_print.py"
)

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


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=True
    )


def _stage_repo(tmp):
    """Build a git repo carrying both the source and deployed tdd-step copies
    plus the contract rabbit_print module. Returns the repo toplevel."""
    root = os.path.join(tmp, "repo")
    src_dir = os.path.join(root, ".claude", "features", "tdd-subagent", "scripts")
    dep_dir = os.path.join(root, ".claude", "agents", "tdd-subagent", "scripts")
    contract_dir = os.path.join(root, ".claude", "features", "contract", "scripts")
    for d in (src_dir, dep_dir, contract_dir):
        os.makedirs(d)
    shutil.copy(TDD_STEP, os.path.join(src_dir, "tdd-step.py"))
    shutil.copy(TDD_STEP, os.path.join(dep_dir, "tdd-step.py"))
    shutil.copy(RABBIT_PRINT, os.path.join(contract_dir, "rabbit_print.py"))

    _git(["init", "-q", "-b", "dev"], root)
    _git(["config", "user.email", "t@t"], root)
    _git(["config", "user.name", "t"], root)
    _git(["add", "."], root)
    _git(["commit", "-q", "-m", "stage"], root)
    return _git(["rev-parse", "--show-toplevel"], root).stdout.strip()


def _run_help(script_path, cwd, env):
    return subprocess.run(
        [sys.executable, script_path, "--help"],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def main():
    if not os.path.isfile(RABBIT_PRINT):
        ko(f"precondition: contract rabbit_print.py not found at {RABBIT_PRINT}")
        return

    env = os.environ.copy()
    env.pop("RABBIT_ROOT", None)

    with tempfile.TemporaryDirectory() as tmp:
        root = _stage_repo(tmp)
        dep = os.path.join(root, ".claude", "agents", "tdd-subagent", "scripts", "tdd-step.py")
        src = os.path.join(root, ".claude", "features", "tdd-subagent", "scripts", "tdd-step.py")

        # Core regression: invoke the DEPLOYED copy. cwd is the repo so the
        # cwd-based git toplevel resolves correctly.
        res = _run_help(dep, root, env)
        if "ModuleNotFoundError" in res.stderr and "rabbit_print" in res.stderr:
            ko("deployed copy: --help still raises ModuleNotFoundError for rabbit_print (#561)")
        elif res.returncode == 0:
            ok("deployed copy: --help loads rabbit_print and exits 0 (#561)")
        else:
            ko(f"deployed copy: --help rc={res.returncode}, stderr={res.stderr!r}")

        # Source-location invocation still works.
        res = _run_help(src, root, env)
        if "ModuleNotFoundError" in res.stderr and "rabbit_print" in res.stderr:
            ko("source copy: --help raises ModuleNotFoundError for rabbit_print")
        elif res.returncode == 0:
            ok("source copy: --help loads rabbit_print and exits 0")
        else:
            ko(f"source copy: --help rc={res.returncode}, stderr={res.stderr!r}")


print(f"running rabbit_print deployed-import tests against {TDD_STEP}")
main()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
