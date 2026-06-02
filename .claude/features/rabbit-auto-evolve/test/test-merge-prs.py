#!/usr/bin/env python3
"""test-merge-prs.py — e2e tests for scripts/merge-prs.py (Inv 6).

Covers the spec'd surface of `scripts/merge-prs.py`:
  - --help smoke
  - skip-on-non-dev-base (defense-in-depth above safety-check.py)
  - skip-on-safety-fail
  - happy path → status: merged
  - refusal invariant: `gh pr merge` is NEVER called when base != dev

Fixtures use a tempdir on PATH carrying:
  - a `gh` shim that dispatches on the subcommand (pr view / pr merge) and
    records every invocation into a call log
  - a `safety-check.py` shim that exits 0 by default (overrideable to non-zero)

The script is configured to find this shim safety-check via the
RABBIT_AUTO_EVOLVE_SCRIPT_DIR env var; when unset it falls back to the
script's own dirname.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "merge-prs.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write_gh_shim(shim_dir, call_log, base_ref="dev", head_ref="feat/x",
                   merge_exit=0, merge_stderr=""):
    """Write a `gh` shim that:
       - dispatches on `pr view --json <field> -q .<field>` and echoes the
         right value
       - dispatches on `pr merge ... --squash --auto` and exits `merge_exit`
       - appends every invocation to `call_log` (one JSON line per call)
    """
    shim = os.path.join(shim_dir, "gh")
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        # Record the call: just the argv joined by ASCII-unit-separator-ish.
        f.write(f'CALL_LOG="{call_log}"\n')
        f.write('printf "%s\\n" "$*" >> "$CALL_LOG"\n')
        f.write(f'BASE_REF={base_ref}\n')
        f.write(f'HEAD_REF={head_ref}\n')
        f.write(f'MERGE_EXIT={merge_exit}\n')
        f.write(f'MERGE_STDERR={merge_stderr!r}\n')
        # Walk args. First arg is subcommand `pr`, second is the action.
        f.write('SUB="$1"; shift\n')
        f.write('ACTION="$1"; shift\n')
        f.write('if [ "$SUB" = "pr" ] && [ "$ACTION" = "view" ]; then\n')
        # Walk for --json and -q
        f.write('  JSON_FIELDS=""\n')
        f.write('  QUERY=""\n')
        f.write('  while [ "$#" -gt 0 ]; do\n')
        f.write('    case "$1" in\n')
        f.write('      --json) JSON_FIELDS="$2"; shift 2 ;;\n')
        f.write('      -q) QUERY="$2"; shift 2 ;;\n')
        f.write('      *) shift ;;\n')
        f.write('    esac\n')
        f.write('  done\n')
        f.write('  case "$QUERY" in\n')
        f.write('    .baseRefName) printf "%s\\n" "$BASE_REF" ;;\n')
        f.write('    .headRefName) printf "%s\\n" "$HEAD_REF" ;;\n')
        f.write('    *) printf "{}\\n" ;;\n')
        f.write('  esac\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('if [ "$SUB" = "pr" ] && [ "$ACTION" = "merge" ]; then\n')
        f.write('  printf "%s" "$MERGE_STDERR" >&2\n')
        f.write('  exit $MERGE_EXIT\n')
        f.write('fi\n')
        f.write('exit 0\n')
    os.chmod(shim, stat.S_IRWXU)


def _write_safety_shim(shim_dir, exit_code=0, stderr_msg=""):
    """Write a `safety-check.py` shim alongside the merge-prs.py script.
    Exit `exit_code` and emit `stderr_msg` on stderr.
    """
    shim = os.path.join(shim_dir, "safety-check.py")
    with open(shim, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import sys\n")
        f.write(f"sys.stderr.write({stderr_msg!r})\n")
        f.write(f"sys.exit({exit_code})\n")
    os.chmod(shim, stat.S_IRWXU)


def _make_env(tmpdir, base_ref="dev", head_ref="feat/x",
              merge_exit=0, merge_stderr="",
              safety_exit=0, safety_stderr=""):
    """Build a sandbox: a bin/ dir on PATH with the gh shim, and a
    script-dir holding the real merge-prs.py copy (via env override) plus a
    safety-check.py shim. Return (cwd=tmpdir, env, call_log_path)."""
    bin_dir = os.path.join(tmpdir, "bin")
    os.makedirs(bin_dir)
    script_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(script_dir)
    call_log = os.path.join(tmpdir, "gh-calls.log")
    open(call_log, "w").close()

    _write_gh_shim(bin_dir, call_log,
                   base_ref=base_ref, head_ref=head_ref,
                   merge_exit=merge_exit, merge_stderr=merge_stderr)
    _write_safety_shim(script_dir, exit_code=safety_exit,
                       stderr_msg=safety_stderr)

    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    return tmpdir, env, call_log


def _gh_calls(call_log):
    with open(call_log) as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _run(cwd, env, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# --help smoke test
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
    fail(f"help: 'usage' missing; stdout={proc.stdout!r} stderr={proc.stderr!r}")
else:
    ok("help: usage text present")


# ---------------------------------------------------------------------------
# Skip-on-non-dev-base: gh shim returns baseRefName=main.
# Expected: status=skipped, reason=base-not-dev. `gh pr merge` MUST NOT
# appear in the call log (refusal invariant).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, base_ref="main")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"skip-base: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"skip-base: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None:
        if not (isinstance(results, list) and len(results) == 1):
            fail(f"skip-base: expected 1-element array, got {results!r}")
        else:
            r = results[0]
            if r.get("pr") != 42:
                fail(f"skip-base: pr field {r.get('pr')!r} != 42")
            if r.get("status") != "skipped":
                fail(f"skip-base: status {r.get('status')!r} != 'skipped'")
            if r.get("reason") != "base-not-dev":
                fail(f"skip-base: reason {r.get('reason')!r} != 'base-not-dev'")
            else:
                ok("skip-base: returns skipped/base-not-dev")
    calls = _gh_calls(call_log)
    if any("pr merge" in c for c in calls):
        fail(f"skip-base: gh pr merge was called; calls={calls!r}")
    else:
        ok("skip-base: gh pr merge was NOT called (refusal invariant)")


# ---------------------------------------------------------------------------
# Skip-on-safety-fail: gh shim returns base=dev; safety-check.py shim
# exits non-zero. Expected: status=skipped, reason=safety-check-failed;
# `gh pr merge` MUST NOT appear in the call log.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(
        td, base_ref="dev", safety_exit=2,
        safety_stderr="Invariant 5 (working tree clean) failed: dirty\n",
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"skip-safety: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"skip-safety: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and isinstance(results, list) and len(results) == 1:
        r = results[0]
        if r.get("status") != "skipped":
            fail(f"skip-safety: status {r.get('status')!r} != 'skipped'")
        if r.get("reason") != "safety-check-failed":
            fail(f"skip-safety: reason {r.get('reason')!r} != "
                 f"'safety-check-failed'")
        else:
            ok("skip-safety: returns skipped/safety-check-failed")
    elif results is not None:
        fail(f"skip-safety: expected 1-element array, got {results!r}")
    calls = _gh_calls(call_log)
    if any("pr merge" in c for c in calls):
        fail(f"skip-safety: gh pr merge was called; calls={calls!r}")
    else:
        ok("skip-safety: gh pr merge was NOT called")


# ---------------------------------------------------------------------------
# Happy path: gh shim returns base=dev, safety-check shim exits 0,
# gh pr merge exits 0. Expected: status=merged; gh pr merge was called.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, base_ref="dev",
                                   safety_exit=0, merge_exit=0)
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"happy: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"happy: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and isinstance(results, list) and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"happy: status {r.get('status')!r} != 'merged'")
        else:
            ok("happy: returns merged")
    elif results is not None:
        fail(f"happy: expected 1-element array, got {results!r}")
    calls = _gh_calls(call_log)
    if not any("pr merge" in c for c in calls):
        fail(f"happy: gh pr merge was NOT called; calls={calls!r}")
    else:
        ok("happy: gh pr merge was called")


# ---------------------------------------------------------------------------
# Happy path — multiple PRs (comma-separated): verify per-PR result rows.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, base_ref="dev",
                                   safety_exit=0, merge_exit=0)
    proc = _run(cwd, env, "1,2,3")
    if proc.returncode != 0:
        fail(f"multi: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"multi: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None:
        if len(results) != 3:
            fail(f"multi: expected 3 results, got {len(results)}")
        else:
            prs = [r.get("pr") for r in results]
            if prs != [1, 2, 3]:
                fail(f"multi: pr field order wrong: {prs!r}")
            statuses = [r.get("status") for r in results]
            if statuses != ["merged", "merged", "merged"]:
                fail(f"multi: statuses {statuses!r}")
            else:
                ok("multi: all three PRs reported merged in order")


# ---------------------------------------------------------------------------
# Failed merge: gh pr merge exits non-zero. Expected: status=failed,
# reason starts with 'gh-merge-failed:'.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log = _make_env(td, base_ref="dev",
                                   safety_exit=0,
                                   merge_exit=1,
                                   merge_stderr="merge conflict")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"merge-fail: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"merge-fail: stdout not JSON: {e}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "failed":
            fail(f"merge-fail: status {r.get('status')!r} != 'failed'")
        elif not r.get("reason", "").startswith("gh-merge-failed"):
            fail(f"merge-fail: reason {r.get('reason')!r} should start "
                 f"with 'gh-merge-failed'")
        else:
            ok("merge-fail: returns failed/gh-merge-failed")


sys.exit(FAIL)
