#!/usr/bin/env python3
"""Inv 54 — tdd-step.py repo-root resolution targets the operating worktree.

Issue #583: under worktree-isolated phase-5 dispatch, the subagent invokes
the MAIN deployed copy of tdd-step.py. The old resolver computed the repo
root from the SCRIPT's own location (`git -C <script_dir> --show-toplevel`),
which under worktree isolation pointed at the MAIN tree — so the scope
marker and feature.json bookkeeping leaked into the dispatcher's main tree
(tripping safety-check Inv 5).

Fix: resolve the repo root from the CURRENT WORKING DIRECTORY instead of the
script location. Under worktree isolation cwd == the worktree → returns the
worktree toplevel; in the headless/main path cwd == the main repo → returns
main. Robust for both.

This is an END-TO-END test: it builds a real git repo + a linked git
worktree, then runs tdd-step.py's resolvers in a subprocess whose cwd is the
worktree but whose SCRIPT copy lives in the main tree, and asserts the
resolved root / scope-marker path all land in the WORKTREE — not the
script's-own/main toplevel.
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


def _make_main_and_worktree(tmp):
    """Create a main git repo and a linked worktree (two distinct toplevels).

    Returns (main_toplevel, worktree_toplevel).
    """
    main = os.path.join(tmp, "main")
    os.makedirs(main)
    _git(["init", "-q", "-b", "dev"], main)
    _git(["config", "user.email", "t@t"], main)
    _git(["config", "user.name", "t"], main)
    with open(os.path.join(main, "f.txt"), "w") as f:
        f.write("x\n")
    _git(["add", "."], main)
    _git(["commit", "-q", "-m", "init"], main)

    wt = os.path.join(tmp, "wt")
    _git(["worktree", "add", "-q", "-b", "feat/x", wt], main)
    # Resolve to canonical toplevels (handles symlinked tmp dirs).
    main_top = _git(["rev-parse", "--show-toplevel"], main).stdout.strip()
    wt_top = _git(["rev-parse", "--show-toplevel"], wt).stdout.strip()
    return main_top, wt_top


# Subprocess body: import tdd-step.py as a module from its (main-tree)
# location, then print the resolver outputs. The cwd is controlled by the
# parent. tdd-step.py imports rabbit_print from the contract feature, so the
# main-tree copy must be used (it sits inside the live repo).
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
        main_top, wt_top = _make_main_and_worktree(tmp)

        # Sanity: the two toplevels are distinct.
        if os.path.realpath(main_top) == os.path.realpath(wt_top):
            ko("precondition: main and worktree toplevels must differ")
            return
        ok("precondition: main and worktree have distinct git toplevels")

        # Ensure RABBIT_ROOT does not short-circuit the resolver under test.
        env = os.environ.copy()
        env.pop("RABBIT_ROOT", None)

        # Core regression: invoke from cwd == worktree. The script copy lives
        # in the MAIN live repo (TDD_STEP), simulating the subagent running
        # the deployed/main copy. The resolver MUST return the WORKTREE root.
        rc, out, err = _run_probe(wt_top, env=env)
        if rc != 0:
            ko(f"probe (cwd=worktree) failed rc={rc}: {err!r}")
            return

        resolved = os.path.realpath(out.get("ROOT", ""))
        if resolved == os.path.realpath(wt_top):
            ok("cwd=worktree -> _repo_root() returns the WORKTREE toplevel (#583)")
        else:
            ko(f"cwd=worktree -> _repo_root() returned {resolved!r}, "
               f"expected worktree {os.path.realpath(wt_top)!r}")

        # The scope-marker path must land under the worktree, not main.
        marker = os.path.realpath(out.get("MARKER", ""))
        if marker.startswith(os.path.realpath(wt_top) + os.sep):
            ok("cwd=worktree -> scope-marker path is under the worktree (#583)")
        else:
            ko(f"cwd=worktree -> scope-marker path {marker!r} not under "
               f"worktree {os.path.realpath(wt_top)!r}")

        # And it MUST NOT leak into the main tree.
        if not marker.startswith(os.path.realpath(main_top) + os.sep):
            ok("cwd=worktree -> scope-marker path does NOT leak into main tree (#583)")
        else:
            ko(f"cwd=worktree -> scope-marker path {marker!r} LEAKED into "
               f"main tree {os.path.realpath(main_top)!r}")

        # Headless/main path preserved: cwd == main repo -> returns main root.
        rc, out, err = _run_probe(main_top, env=env)
        if rc != 0:
            ko(f"probe (cwd=main) failed rc={rc}: {err!r}")
            return
        resolved_main = os.path.realpath(out.get("ROOT", ""))
        if resolved_main == os.path.realpath(main_top):
            ok("cwd=main -> _repo_root() returns the main toplevel (headless path)")
        else:
            ko(f"cwd=main -> _repo_root() returned {resolved_main!r}, "
               f"expected main {os.path.realpath(main_top)!r}")

        # Plugin-mode preserved: when RABBIT_ROOT is an UNRELATED directory
        # (a different git repo or no git repo at all), RABBIT_ROOT wins even
        # when cwd is a linked worktree. Simulate plugin mode by using a second
        # temp directory as RABBIT_ROOT (no git relationship to cwd's worktree).
        import tempfile as _tf
        with _tf.TemporaryDirectory() as plugin_root:
            env2 = os.environ.copy()
            env2["RABBIT_ROOT"] = plugin_root
            rc2, out2, err2 = _run_probe(wt_top, env=env2)
            if rc2 == 0 and os.path.realpath(out2.get("ROOT", "")) == os.path.realpath(plugin_root):
                ok("RABBIT_ROOT (unrelated repo) + cwd=worktree -> "
                   "RABBIT_ROOT honored (plugin path)")
            else:
                ko(f"RABBIT_ROOT path: rc={rc2} ROOT={out2.get('ROOT')!r} "
                   f"err={err2!r}")

        # Worktree of SAME repo: when RABBIT_ROOT is the main checkout and
        # cwd is a linked worktree of the same repo, cwd wins (#1202 fix).
        env3 = os.environ.copy()
        env3["RABBIT_ROOT"] = main_top
        rc3, out3, err3 = _run_probe(wt_top, env=env3)
        if rc3 == 0 and os.path.realpath(out3.get("ROOT", "")) == os.path.realpath(wt_top):
            ok("RABBIT_ROOT=main + cwd=linked-worktree (same repo) -> "
               "cwd wins over RABBIT_ROOT (#1202)")
        else:
            ko(f"same-repo worktree path: rc={rc3} ROOT={out3.get('ROOT')!r} "
               f"err={err3!r}")


print(f"running repo-root cwd-resolution tests against {TDD_STEP}")
main()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
