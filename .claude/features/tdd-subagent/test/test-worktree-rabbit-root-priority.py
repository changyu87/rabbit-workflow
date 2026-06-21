#!/usr/bin/env python3
"""Inv 66 — tdd-step.py prefers cwd-based worktree root over RABBIT_ROOT (#1202).

When RABBIT_ROOT is set (pointing at the MAIN checkout) but tdd-step.py is
invoked from within a per-session LINKED git worktree (cwd != RABBIT_ROOT),
the resolver MUST return the cwd-based git toplevel (the worktree), NOT
RABBIT_ROOT.

Consequences of the bug:
  1. The spec-update -> test-red diff check (git -C REPO_ROOT diff HEAD) reads
     the MAIN tree where the worktree's spec edit is invisible, causing a
     spurious --spec-no-change-reason demand.
  2. TDD state writes (scope marker, feature.json) leak into the main checkout
     instead of the worktree.

This is an END-TO-END test: it builds a real git repo + a linked git worktree,
then runs the tdd-step.py resolver in a subprocess whose cwd is the linked
worktree but whose RABBIT_ROOT env var points at the main checkout, and asserts
the resolved root / scope-marker path land in the WORKTREE.

The fix must not break plugin mode: when RABBIT_ROOT points at a non-worktree
path (e.g. a vendored <host>/.rabbit/ subdirectory), RABBIT_ROOT continues to
win.
"""
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TDD_STEP = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")

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


def _make_main_and_linked_worktree(tmp):
    """Create a main git repo and a linked worktree.

    Returns (main_toplevel, linked_worktree_toplevel).
    """
    main = os.path.join(tmp, "main")
    os.makedirs(main)
    _git(["init", "-q", "-b", "dev"], main)
    _git(["config", "user.email", "t@t"], main)
    _git(["config", "user.name", "t"], main)
    with open(os.path.join(main, "seed.txt"), "w") as f:
        f.write("x\n")
    _git(["add", "."], main)
    _git(["commit", "-q", "-m", "init"], main)

    wt = os.path.join(tmp, "linked-wt")
    _git(["worktree", "add", "-q", "-b", "feat/x", wt], main)

    # Resolve canonical toplevels (handles symlinked tmp dirs).
    main_top = _git(["rev-parse", "--show-toplevel"], main).stdout.strip()
    wt_top = _git(["rev-parse", "--show-toplevel"], wt).stdout.strip()
    return main_top, wt_top


# Probe body: import tdd-step.py as a module from its location in the live
# repo, then print the resolver outputs. The cwd is controlled by the parent.
_PROBE = (
    "import importlib.util, os, sys\n"
    "spec = importlib.util.spec_from_file_location('tdd_step_probe', %r)\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(m)\n"
    "root = m._repo_root()\n"
    "marker = m._scope_marker_path_for_abort(root, 'tdd-subagent')\n"
    "print('ROOT=' + root)\n"
    "print('MARKER=' + marker)\n"
)


def _run_probe(cwd, env=None):
    res = subprocess.run(
        [sys.executable, "-c", _PROBE % TDD_STEP],
        cwd=cwd, capture_output=True, text=True, env=env,
    )
    out = {}
    for line in res.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return res.returncode, out, res.stderr


def main():
    with tempfile.TemporaryDirectory() as tmp:
        main_top, wt_top = _make_main_and_linked_worktree(tmp)

        # Sanity: the two toplevels are distinct.
        if os.path.realpath(main_top) != os.path.realpath(wt_top):
            ok("precondition: main and linked worktree have distinct toplevels")
        else:
            ko("precondition: main and worktree toplevels must differ")
            return

        # -----------------------------------------------------------
        # Core regression (#1202): RABBIT_ROOT == main, cwd == linked worktree.
        # The resolver MUST return the WORKTREE root, not RABBIT_ROOT.
        # -----------------------------------------------------------
        env_wt = os.environ.copy()
        env_wt["RABBIT_ROOT"] = main_top  # stale: points at main checkout

        rc, out, err = _run_probe(wt_top, env=env_wt)
        if rc != 0:
            ko(f"probe (RABBIT_ROOT=main, cwd=worktree) failed rc={rc}: {err!r}")
            return

        resolved = os.path.realpath(out.get("ROOT", ""))
        expected_wt = os.path.realpath(wt_top)

        if resolved == expected_wt:
            ok("RABBIT_ROOT=main + cwd=linked-worktree -> _repo_root() returns "
               "WORKTREE root (#1202)")
        else:
            ko(f"RABBIT_ROOT=main + cwd=linked-worktree -> _repo_root() returned "
               f"{resolved!r}, expected worktree {expected_wt!r}")

        # Scope-marker path must land under the worktree, NOT under main.
        marker = os.path.realpath(out.get("MARKER", ""))
        if marker.startswith(expected_wt + os.sep):
            ok("RABBIT_ROOT=main + cwd=linked-worktree -> scope-marker is under "
               "WORKTREE (#1202)")
        else:
            ko(f"scope-marker {marker!r} not under worktree {expected_wt!r}")

        if not marker.startswith(os.path.realpath(main_top) + os.sep):
            ok("RABBIT_ROOT=main + cwd=linked-worktree -> scope-marker does NOT "
               "leak into main tree (#1202)")
        else:
            ko(f"scope-marker {marker!r} leaked into main {os.path.realpath(main_top)!r}")

        # -----------------------------------------------------------
        # Back-compat (plugin-mode): RABBIT_ROOT != cwd but cwd is NOT a
        # linked worktree (cwd == main_top). RABBIT_ROOT must win or agree.
        # -----------------------------------------------------------
        env_plugin = os.environ.copy()
        env_plugin["RABBIT_ROOT"] = main_top

        rc2, out2, err2 = _run_probe(main_top, env=env_plugin)
        if rc2 == 0 and os.path.realpath(out2.get("ROOT", "")) == os.path.realpath(main_top):
            ok("RABBIT_ROOT=main + cwd=main (no linked worktree) -> RABBIT_ROOT "
               "honored (plugin back-compat)")
        else:
            ko(f"plugin back-compat: rc={rc2} ROOT={out2.get('ROOT')!r} "
               f"err={err2!r}")

        # -----------------------------------------------------------
        # No-RABBIT_ROOT path preserved (Inv 54): cwd=worktree wins.
        # -----------------------------------------------------------
        env_no_rr = os.environ.copy()
        env_no_rr.pop("RABBIT_ROOT", None)

        rc3, out3, err3 = _run_probe(wt_top, env=env_no_rr)
        if rc3 != 0:
            ko(f"probe (no RABBIT_ROOT, cwd=worktree) failed rc={rc3}: {err3!r}")
        else:
            resolved3 = os.path.realpath(out3.get("ROOT", ""))
            if resolved3 == expected_wt:
                ok("no RABBIT_ROOT + cwd=worktree -> _repo_root() returns WORKTREE "
                   "(Inv 54 back-compat)")
            else:
                ko(f"no RABBIT_ROOT + cwd=worktree -> _repo_root() returned "
                   f"{resolved3!r}, expected {expected_wt!r}")


print(f"running worktree-RABBIT_ROOT-priority tests against {TDD_STEP}")
main()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
