#!/usr/bin/env python3
"""test-merge-prs.py — e2e tests for scripts/merge-prs.py (Inv 6).

Covers the spec'd surface of `scripts/merge-prs.py`:
  - --help smoke
  - skip-on-non-dev-base (defense-in-depth above safety-check.py)
  - skip-on-safety-fail
  - happy path → status: merged
  - refusal invariant: `gh pr merge` is NEVER called when base != dev
  - close-after-merge (issue #392): explicit issue close after a dev merge

Fixtures use a tempdir on PATH carrying:
  - a `gh` shim that dispatches on the subcommand (pr view / pr merge) and
    records every invocation into a call log
  - a `safety-check.py` shim that exits 0 by default (overrideable to non-zero)
  - an `item-status.py` shim (in a separate rabbit-issue scripts dir) that
    records every invocation into a call log

The script is configured to find these shims via the
RABBIT_AUTO_EVOLVE_SCRIPT_DIR / RABBIT_ISSUE_SCRIPT_DIR env vars; when unset
the safety-check.py path falls back to the script's own dirname.
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
                   merge_exit=0, merge_stderr="", pr_body="",
                   merge_sha="abc1234"):
    """Write a `gh` shim that:
       - dispatches on `pr view --json <field> -q .<field>` and echoes the
         right value (baseRefName, headRefName, body, mergeCommit.oid)
       - dispatches on `pr merge ... --squash` and exits `merge_exit`
       - appends every invocation to `call_log` (one JSON line per call)
    """
    # The PR body may contain newlines; write it to a sidecar file the shim
    # `cat`s, so shell escaping never mangles the embedded newlines.
    body_file = os.path.join(shim_dir, "pr-body.txt")
    with open(body_file, "w") as bf:
        bf.write(pr_body)
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
        f.write(f'BODY_FILE={body_file!r}\n')
        f.write(f'MERGE_SHA={merge_sha!r}\n')
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
        f.write('    .body) cat "$BODY_FILE" ;;\n')
        f.write('    .mergeCommit.oid) printf "%s\\n" "$MERGE_SHA" ;;\n')
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


def _write_item_status_shim(shim_dir, call_log, exit_code=0, stderr_msg=""):
    """Write an `item-status.py` shim into a rabbit-issue scripts dir.
    Records every invocation argv into `call_log` (one line per call),
    then exits `exit_code` (emitting `stderr_msg` on stderr first).
    """
    shim = os.path.join(shim_dir, "item-status.py")
    with open(shim, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import sys\n")
        f.write(f"with open({call_log!r}, 'a') as _f:\n")
        f.write("    _f.write(' '.join(sys.argv[1:]) + '\\n')\n")
        f.write(f"sys.stderr.write({stderr_msg!r})\n")
        f.write(f"sys.exit({exit_code})\n")
    os.chmod(shim, stat.S_IRWXU)


def _make_env(tmpdir, base_ref="dev", head_ref="feat/x",
              merge_exit=0, merge_stderr="",
              safety_exit=0, safety_stderr="",
              pr_body="", merge_sha="abc1234",
              item_status_exit=0, item_status_stderr=""):
    """Build a sandbox: a bin/ dir on PATH with the gh shim, and a
    script-dir holding the real merge-prs.py copy (via env override) plus a
    safety-check.py shim, plus an item-status.py shim in a separate
    rabbit-issue scripts dir (via env override). Return
    (cwd=tmpdir, env, call_log_path, item_status_log_path)."""
    bin_dir = os.path.join(tmpdir, "bin")
    os.makedirs(bin_dir)
    script_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(script_dir)
    issue_dir = os.path.join(tmpdir, "issue-scripts")
    os.makedirs(issue_dir)
    call_log = os.path.join(tmpdir, "gh-calls.log")
    open(call_log, "w").close()
    item_status_log = os.path.join(tmpdir, "item-status-calls.log")
    open(item_status_log, "w").close()

    _write_gh_shim(bin_dir, call_log,
                   base_ref=base_ref, head_ref=head_ref,
                   merge_exit=merge_exit, merge_stderr=merge_stderr,
                   pr_body=pr_body, merge_sha=merge_sha)
    _write_safety_shim(script_dir, exit_code=safety_exit,
                       stderr_msg=safety_stderr)
    _write_item_status_shim(issue_dir, item_status_log,
                            exit_code=item_status_exit,
                            stderr_msg=item_status_stderr)

    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_ISSUE_SCRIPT_DIR"] = issue_dir
    return tmpdir, env, call_log, item_status_log


def _gh_calls(call_log):
    with open(call_log) as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _item_status_calls(item_status_log):
    with open(item_status_log) as f:
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main")
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
    cwd, env, call_log, item_status_log = _make_env(
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="dev",
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="dev",
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
# Regression (issue #429): `gh pr merge` MUST NOT pass `--auto`. The --auto
# flag requires the repo to have auto-merge enabled (enablePullRequestAuto
# Merge); on repos without it, `gh pr merge --auto` fails for any PR that is
# not immediately mergeable with `Auto merge is not allowed for this
# repository`. The fix is a direct squash merge. This test asserts the merge
# invocation recorded in the gh call log does NOT contain `--auto` (or, if
# it ever did, the script would have to demonstrate a direct-merge fallback —
# this test enforces the simpler invariant: no --auto on the merge call).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="dev",
                                                    safety_exit=0, merge_exit=0)
    proc = _run(cwd, env, "42")
    calls = _gh_calls(call_log)
    merge_calls = [c for c in calls if "pr merge" in c]
    if not merge_calls:
        fail(f"no-auto: gh pr merge was NOT called; calls={calls!r}")
    elif any("--auto" in c for c in merge_calls):
        fail(f"no-auto: gh pr merge invoked with --auto (issue #429): "
             f"{merge_calls!r}")
    else:
        ok("no-auto: gh pr merge invoked without --auto (issue #429)")
    # The merge must still be a squash merge.
    if merge_calls and not any("--squash" in c for c in merge_calls):
        fail(f"no-auto: gh pr merge missing --squash; {merge_calls!r}")
    elif merge_calls:
        ok("no-auto: gh pr merge still uses --squash")


# ---------------------------------------------------------------------------
# Failed merge: gh pr merge exits non-zero. Expected: status=failed,
# reason starts with 'gh-merge-failed:'.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="dev",
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


# ===========================================================================
# Issue #392 — explicit close-after-merge.
#
# Auto-evolve PRs target `dev`, never the default branch `main`, so GitHub's
# `Fixes #N` / `Closes #N` auto-close never fires. After a successful merge,
# merge-prs.py MUST parse the merged PR body for issue references and invoke
# item-status.py close on each referenced issue.
# ===========================================================================

# ---------------------------------------------------------------------------
# Close-after-merge happy path: PR body references three issues across the
# three accepted keywords (Fixes / Closes / Resolves), case-insensitively.
# Expected: status=merged; item-status.py close invoked once per distinct
# issue with --reason completed and a --comment recording the merge SHA;
# result row carries a sorted closed_issues list.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    body = "Some change.\n\nFixes #11\nCloses #22\nresolves #33\n"
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_body=body, merge_sha="deadbee",
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"close-after-merge: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"close-after-merge: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and isinstance(results, list) and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"close-after-merge: status {r.get('status')!r} != 'merged'")
        else:
            ok("close-after-merge: status merged")
        if sorted(r.get("closed_issues", [])) != [11, 22, 33]:
            fail(f"close-after-merge: closed_issues "
                 f"{r.get('closed_issues')!r} != [11, 22, 33]")
        else:
            ok("close-after-merge: closed_issues == [11, 22, 33]")
    elif results is not None:
        fail(f"close-after-merge: expected 1-element array, got {results!r}")

    is_calls = _item_status_calls(item_status_log)
    if len(is_calls) != 3:
        fail(f"close-after-merge: expected 3 item-status calls, "
             f"got {len(is_calls)}: {is_calls!r}")
    else:
        ok("close-after-merge: item-status.py invoked 3 times")
    closed_nums = set()
    for c in is_calls:
        parts = c.split()
        if parts[:1] != ["close"]:
            fail(f"close-after-merge: call not a close subcommand: {c!r}")
            continue
        closed_nums.add(parts[1])
        if "--reason" not in parts or \
                parts[parts.index("--reason") + 1] != "completed":
            fail(f"close-after-merge: call missing --reason completed: {c!r}")
        if "--comment" not in parts:
            fail(f"close-after-merge: call missing --comment: {c!r}")
        elif "deadbee" not in c:
            fail(f"close-after-merge: --comment missing SHA 'deadbee': {c!r}")
    if closed_nums == {"11", "22", "33"}:
        ok("close-after-merge: closed issues 11/22/33 with reason+SHA comment")
    else:
        fail(f"close-after-merge: closed issue numbers {closed_nums!r} "
             f"!= {{11,22,33}}")


# ---------------------------------------------------------------------------
# No references in body: item-status.py is NOT invoked; closed_issues empty.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_body="No issue refs here.\n",
    )
    proc = _run(cwd, env, "42")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"no-refs: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("status") != "merged":
            fail(f"no-refs: status {results[0].get('status')!r} != 'merged'")
        if results[0].get("closed_issues", []) != []:
            fail(f"no-refs: closed_issues {results[0].get('closed_issues')!r} "
                 f"!= []")
        else:
            ok("no-refs: closed_issues empty")
    if _item_status_calls(item_status_log):
        fail("no-refs: item-status.py was invoked for a body with no refs")
    else:
        ok("no-refs: item-status.py NOT invoked")


# ---------------------------------------------------------------------------
# item-status.py failure is non-fatal: merge still reports merged; a stderr
# warning is emitted; the issue is recorded under close_failed, not
# closed_issues. (Backward-compatibility acceptance criterion.)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_body="Fixes #99\n",
        item_status_exit=1, item_status_stderr="not rabbit-managed\n",
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"close-fail: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"close-fail: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"close-fail: status {r.get('status')!r} != 'merged' "
                 f"(close failure must not fail the merge)")
        else:
            ok("close-fail: merge still reports merged")
        if r.get("closed_issues", []) != []:
            fail(f"close-fail: failed issue leaked into closed_issues: "
                 f"{r.get('closed_issues')!r}")
        if r.get("close_failed", []) != [99]:
            fail(f"close-fail: close_failed {r.get('close_failed')!r} != [99]")
        else:
            ok("close-fail: failed issue recorded under close_failed")
    if "99" not in proc.stderr:
        fail(f"close-fail: expected a stderr warning mentioning 99; "
             f"stderr={proc.stderr!r}")
    else:
        ok("close-fail: stderr warning emitted for failed close")


# ---------------------------------------------------------------------------
# Refusal invariant for close: item-status.py is NEVER invoked when the
# merge itself did not succeed (e.g. base != dev).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", pr_body="Fixes #5\n",
    )
    _run(cwd, env, "42")
    if _item_status_calls(item_status_log):
        fail("close-skip: item-status.py invoked for a non-merged PR")
    else:
        ok("close-skip: item-status.py NOT invoked when merge was skipped")


sys.exit(FAIL)
