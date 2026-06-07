#!/usr/bin/env python3
"""test-cleanup-branches.py — e2e tests for scripts/cleanup-branches.py (Inv 6).

Covers the spec'd surface of `scripts/cleanup-branches.py`:
  - --help smoke
  - skip-on-non-feat-branch (defense-in-depth above safety-check.py): no
    deletion command runs; stderr warning emitted
  - happy path → status: deleted; both `git branch -D` and
    `git push origin --delete` are called

Fixtures use a tempdir on PATH carrying:
  - a `gh` shim that responds to `gh pr view --json headRefName`
  - a `git` shim that records `git branch -D` and `git push origin --delete`
    invocations into a call log
  - a `safety-check.py` shim alongside the script that exits 0 (overrideable)

The script is configured to find the shim safety-check via the
RABBIT_AUTO_EVOLVE_SCRIPT_DIR env var.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "cleanup-branches.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write_gh_shim(shim_dir, call_log, head_ref="feat/x"):
    shim = os.path.join(shim_dir, "gh")
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        f.write(f'CALL_LOG="{call_log}"\n')
        f.write('printf "gh %s\\n" "$*" >> "$CALL_LOG"\n')
        f.write(f'HEAD_REF={head_ref}\n')
        f.write('SUB="$1"; shift\n')
        f.write('ACTION="$1"; shift\n')
        f.write('if [ "$SUB" = "pr" ] && [ "$ACTION" = "view" ]; then\n')
        f.write('  QUERY=""\n')
        f.write('  while [ "$#" -gt 0 ]; do\n')
        f.write('    case "$1" in\n')
        f.write('      --json) shift 2 ;;\n')
        f.write('      -q) QUERY="$2"; shift 2 ;;\n')
        f.write('      *) shift ;;\n')
        f.write('    esac\n')
        f.write('  done\n')
        f.write('  case "$QUERY" in\n')
        f.write('    .headRefName) printf "%s\\n" "$HEAD_REF" ;;\n')
        f.write('    *) printf "{}\\n" ;;\n')
        f.write('  esac\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('exit 0\n')
    os.chmod(shim, stat.S_IRWXU)


def _write_git_shim(shim_dir, call_log,
                    branch_delete_exit=0, push_delete_exit=0):
    """Write a `git` shim that records `git branch -D X` and
    `git push origin --delete X` calls into the log. For any other git
    subcommand, fall through to the real git binary."""
    shim = os.path.join(shim_dir, "git")
    # Resolve a real git path that bypasses our shim dir.
    # Just hard-code a couple of common locations and fall back to PATH
    # excluding shim_dir at runtime via env tweak.
    real_git = subprocess.check_output(["which", "git"]).decode().strip()
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        f.write(f'CALL_LOG="{call_log}"\n')
        f.write(f'REAL_GIT="{real_git}"\n')
        f.write(f'BD_EXIT={branch_delete_exit}\n')
        f.write(f'PD_EXIT={push_delete_exit}\n')
        # Detect `git branch -D X`
        f.write('if [ "$1" = "branch" ] && [ "$2" = "-D" ]; then\n')
        f.write('  printf "git branch -D %s\\n" "$3" >> "$CALL_LOG"\n')
        f.write('  exit $BD_EXIT\n')
        f.write('fi\n')
        # Detect `git push origin --delete X`
        f.write('if [ "$1" = "push" ] && [ "$2" = "origin" ] && '
                '[ "$3" = "--delete" ]; then\n')
        f.write('  printf "git push origin --delete %s\\n" "$4" '
                '>> "$CALL_LOG"\n')
        f.write('  exit $PD_EXIT\n')
        f.write('fi\n')
        # Otherwise delegate to real git.
        f.write('exec "$REAL_GIT" "$@"\n')
    os.chmod(shim, stat.S_IRWXU)


def _write_safety_shim(shim_dir, exit_code=0, stderr_msg=""):
    shim = os.path.join(shim_dir, "safety-check.py")
    with open(shim, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import sys\n")
        f.write(f"sys.stderr.write({stderr_msg!r})\n")
        f.write(f"sys.exit({exit_code})\n")
    os.chmod(shim, stat.S_IRWXU)


def _make_env(tmpdir, head_ref="feat/x",
              branch_delete_exit=0, push_delete_exit=0,
              safety_exit=0):
    bin_dir = os.path.join(tmpdir, "bin")
    os.makedirs(bin_dir)
    script_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(script_dir)
    call_log = os.path.join(tmpdir, "calls.log")
    open(call_log, "w").close()

    _write_gh_shim(bin_dir, call_log, head_ref=head_ref)
    _write_git_shim(bin_dir, call_log,
                    branch_delete_exit=branch_delete_exit,
                    push_delete_exit=push_delete_exit)
    _write_safety_shim(script_dir, exit_code=safety_exit)

    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    return tmpdir, env, call_log


def _calls(call_log):
    with open(call_log) as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _run(cwd, env, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# --help smoke
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail(f"help: 'usage' missing; stdout={proc.stdout!r}")
else:
    ok("help: usage text present")


# ---------------------------------------------------------------------------
# Skip-on-non-feat-branch: gh shim returns headRefName=main.
# Expected: status=skipped, reason=non-feat-branch; stderr warning;
# NO `git branch -D` or `git push --delete` calls.
# ---------------------------------------------------------------------------
for head in ("main", "dev", "release/v1.0", "hotfix/foo"):
    with tempfile.TemporaryDirectory() as td:
        cwd, env, call_log = _make_env(td, head_ref=head)
        proc = _run(cwd, env, "42")
        if proc.returncode != 0:
            fail(f"skip-{head}: expected exit 0, got {proc.returncode}; "
                 f"stderr={proc.stderr!r}")
        try:
            results = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            fail(f"skip-{head}: stdout not JSON: {e}; stdout={proc.stdout!r}")
            results = None
        if results is not None and len(results) == 1:
            r = results[0]
            if r.get("status") != "skipped":
                fail(f"skip-{head}: status {r.get('status')!r} != 'skipped'")
            elif r.get("reason") != "non-feat-branch":
                fail(f"skip-{head}: reason {r.get('reason')!r} != "
                     f"'non-feat-branch'")
            elif r.get("branch") != head:
                fail(f"skip-{head}: branch field {r.get('branch')!r} != {head!r}")
            else:
                ok(f"skip-{head}: returns skipped/non-feat-branch")
        if not proc.stderr.strip():
            fail(f"skip-{head}: expected stderr warning, got empty")
        else:
            ok(f"skip-{head}: stderr warning emitted")
        calls = _calls(call_log)
        if any("branch -D" in c or "push origin --delete" in c for c in calls):
            fail(f"skip-{head}: deletion command called; calls={calls!r}")
        else:
            ok(f"skip-{head}: no deletion command called (refusal invariant)")


# ---------------------------------------------------------------------------
# Skip-on-safety-fail: head is feat/x but safety-check returns non-zero.
# Expected: status=skipped, reason=safety-check-failed; no deletion calls.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, head_ref="feat/x", safety_exit=2)
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"safety-fail: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        results = None
        fail("safety-fail: stdout not JSON")
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "skipped":
            fail(f"safety-fail: status {r.get('status')!r} != 'skipped'")
        elif r.get("reason") != "safety-check-failed":
            fail(f"safety-fail: reason {r.get('reason')!r}")
        else:
            ok("safety-fail: returns skipped/safety-check-failed")
    calls = _calls(call_log)
    if any("branch -D" in c or "push origin --delete" in c for c in calls):
        fail(f"safety-fail: deletion command called; calls={calls!r}")
    else:
        ok("safety-fail: no deletion command called")


# ---------------------------------------------------------------------------
# Happy path: head=feat/xyz, safety passes, both deletes succeed.
# Expected: status=deleted, branch=feat/xyz; both deletion commands called.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, head_ref="feat/xyz",
                                   branch_delete_exit=0, push_delete_exit=0,
                                   safety_exit=0)
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"happy: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        results = None
        fail("happy: stdout not JSON")
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "deleted":
            fail(f"happy: status {r.get('status')!r} != 'deleted'")
        elif r.get("branch") != "feat/xyz":
            fail(f"happy: branch {r.get('branch')!r}")
        else:
            ok("happy: returns deleted/feat/xyz")
    calls = _calls(call_log)
    if not any("git branch -D feat/xyz" in c for c in calls):
        fail(f"happy: git branch -D feat/xyz not called; calls={calls!r}")
    else:
        ok("happy: git branch -D feat/xyz called")
    if not any("git push origin --delete feat/xyz" in c for c in calls):
        fail(f"happy: git push origin --delete feat/xyz not called; "
             f"calls={calls!r}")
    else:
        ok("happy: git push origin --delete feat/xyz called")


# ---------------------------------------------------------------------------
# git branch -D failure is acceptable (best-effort) but push-delete failure
# yields status=failed.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, head_ref="feat/xyz",
                                   branch_delete_exit=1, push_delete_exit=0,
                                   safety_exit=0)
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"branch-D-fail: expected exit 0, got {proc.returncode}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("status") != "deleted":
            fail(f"branch-D-fail: status {results[0].get('status')!r} != "
                 f"'deleted' — local branch -D non-zero is best-effort")
        else:
            ok("branch-D-fail: local branch -D failure is tolerated")

with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, head_ref="feat/xyz",
                                   branch_delete_exit=0, push_delete_exit=1,
                                   safety_exit=0)
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"push-fail: expected exit 0, got {proc.returncode}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("status") != "failed":
            fail(f"push-fail: status {results[0].get('status')!r} != 'failed'")
        else:
            ok("push-fail: returns failed when push --delete fails")


sys.exit(FAIL)
