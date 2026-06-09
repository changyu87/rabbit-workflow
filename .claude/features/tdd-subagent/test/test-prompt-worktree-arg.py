#!/usr/bin/env python3
"""Inv 65 — `--worktree`/`--cwd` anchors emitted prompt paths to an absolute
worktree root (issue #1128, vendored Strategy D).

In vendored mode the Step-5 TDD-subagent dispatch (the Agent call) has no cwd
parameter, so the subagent inherits the host `.rabbit` cwd (on main). Its scope
marker / git add+commit / publish repo_root / UNLOCK operations then resolve
against the HOST tree instead of the per-session Strategy D worktree, so commits
land on host main. The robust fix bakes ABSOLUTE worktree paths into the emitted
dispatch prompt so the subagent operates in the worktree regardless of inherited
cwd.

This e2e test runs dispatch-tdd-subagent.py as a subprocess in three scenarios:

  A) WITH --worktree <abs>: the path slots (feature_dir, tdd_step_py,
     repo_root, scope_marker_path, tdd_report_path) are emitted as ABSOLUTE
     paths under the worktree root:
       - repo_root slot resolves to the worktree (publish-loop line is
         <worktree>/.claude/features/contract/lib/publish.py),
       - feature_dir / tdd_step_py begin with <worktree>/,
       - LOCK/UNLOCK scope-marker line uses the absolute
         <worktree>/.rabbit-scope-active-tdd-subagent form,
       - STEP 7 tdd-report Path begins with <worktree>/.

  B) --cwd is an accepted alias for --worktree (same anchoring).

  C) Standalone / NO --worktree: byte-identical to today — relative slots and
     repo_root='.'. This is the hard back-compat guarantee.
"""
import os
import re
import subprocess
import sys

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


def _strip_spec_block(prompt):
    return re.sub(
        r"═+\nSPEC\n═+\n.*?(?=═+\nE2E TEST RULE)",
        "[[SPEC BLOCK STRIPPED]]\n",
        prompt,
        count=1,
        flags=re.DOTALL,
    )


def _extract_lock_body(prompt):
    m = re.search(r"STEP 1 — LOCK\n═+\n(.*?)\n═+\nSTEP 2", prompt, re.DOTALL)
    return m.group(1) if m else None


def _extract_unlock_body(prompt):
    m = re.search(r"STEP 8 — UNLOCK\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
    return m.group(1) if m else None


env = os.environ.copy()
env.pop("RABBIT_ROOT", None)

# A worktree root the dispatcher must NOT need to exist on disk to anchor
# paths against — anchoring is pure string composition.
WT = os.path.join(REPO_ROOT, ".claude", "worktrees", "agent-test1128")


def _run(*extra):
    return subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "tdd-subagent",
         "--spec", SPEC_PATH, *extra],
        capture_output=True, text=True, env=env,
    )


def _assert_worktree_anchored(label, prompt):
    body = _strip_spec_block(prompt)
    wt_prefix = WT.rstrip("/") + "/"

    # repo_root slot resolves to the worktree (publish-loop line).
    if f"{wt_prefix}.claude/features/contract/lib/publish.py" in body:
        ok(f"{label}: repo_root slot is the worktree (publish.py absolute)")
    else:
        ko(f"{label}: repo_root slot not anchored at worktree (publish.py "
           "not absolute under worktree)")

    # feature_dir absolute under worktree.
    if f"{wt_prefix}.claude/features/tdd-subagent/test/" in body:
        ok(f"{label}: feature_dir is absolute under worktree")
    else:
        ko(f"{label}: feature_dir not absolute under worktree")

    # tdd_step_py absolute under worktree.
    if (f"{wt_prefix}.claude/features/tdd-subagent/scripts/tdd-step.py"
            in body):
        ok(f"{label}: tdd_step_py is absolute under worktree")
    else:
        ko(f"{label}: tdd_step_py not absolute under worktree")

    # LOCK/UNLOCK scope-marker absolute under worktree.
    lock_body = _extract_lock_body(prompt)
    unlock_body = _extract_unlock_body(prompt)
    marker = f"{wt_prefix}.rabbit-scope-active-tdd-subagent"
    if lock_body and re.search(
            r"touch\s+" + re.escape(marker) + r"\b", lock_body):
        ok(f"{label}: LOCK uses absolute worktree scope marker")
    else:
        ko(f"{label}: LOCK scope-marker not absolute under worktree")
    if unlock_body and re.search(
            r"rm -f\s+" + re.escape(marker) + r"\b", unlock_body):
        ok(f"{label}: UNLOCK uses absolute worktree scope marker")
    else:
        ko(f"{label}: UNLOCK scope-marker not absolute under worktree")

    # STEP 7 tdd-report Path absolute under worktree.
    m = re.search(
        r"^\s*Path:\s*(\S+tdd-report-tdd-subagent\.json)\s*$",
        prompt, re.MULTILINE)
    if m is None:
        ko(f"{label}: no STEP 7 'Path:' line for tdd-report found")
    elif m.group(1).startswith(wt_prefix):
        ok(f"{label}: STEP 7 tdd-report Path is absolute under worktree")
    else:
        ko(f"{label}: STEP 7 tdd-report Path not under worktree — got "
           f"{m.group(1)!r}")


# ---------------------------------------------------------------------------
# Scenario A: --worktree anchors all slots absolute.
# ---------------------------------------------------------------------------
res = _run("--worktree", WT)
if res.returncode != 0:
    ko(f"scenario A: dispatch --worktree failed rc={res.returncode}: "
       f"{res.stderr!r}")
else:
    _assert_worktree_anchored("scenario A (--worktree)", res.stdout)


# ---------------------------------------------------------------------------
# Scenario B: --cwd is an accepted alias.
# ---------------------------------------------------------------------------
res = _run("--cwd", WT)
if res.returncode != 0:
    ko(f"scenario B: dispatch --cwd failed rc={res.returncode}: "
       f"{res.stderr!r}")
else:
    _assert_worktree_anchored("scenario B (--cwd)", res.stdout)


# ---------------------------------------------------------------------------
# Scenario C: NO --worktree is byte-identical to today.
# ---------------------------------------------------------------------------
baseline = _run()
if baseline.returncode != 0:
    ko(f"scenario C: baseline dispatch failed rc={baseline.returncode}: "
       f"{baseline.stderr!r}")
else:
    body = _strip_spec_block(baseline.stdout)
    # Relative slots preserved.
    if "./.claude/features/contract/lib/publish.py" in body:
        ok("scenario C: standalone repo_root slot is '.' (unchanged)")
    else:
        ko("scenario C: standalone repo_root slot not '.'")
    if WT not in body:
        ok("scenario C: standalone prompt carries no worktree prefix")
    else:
        ko("scenario C: standalone prompt unexpectedly carries worktree path")
    # The dispatcher run WITHOUT --worktree must produce a prompt with the
    # same path-slot shape as before this change. Cross-check against the
    # relative-paths invariant tokens (Inv 58).
    lock_body = _extract_lock_body(baseline.stdout)
    if lock_body and re.search(
            r"touch\s+\.rabbit-scope-active-tdd-subagent\b", lock_body):
        ok("scenario C: standalone LOCK uses relative scope marker "
           "(byte-compatible with Inv 58)")
    else:
        ko("scenario C: standalone LOCK scope-marker not relative")


report(passed, failed)
