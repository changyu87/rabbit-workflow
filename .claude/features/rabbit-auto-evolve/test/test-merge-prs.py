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
                   merge_exit=0, merge_stderr="", pr_body="", pr_title="",
                   merge_sha="abc1234"):
    """Write a `gh` shim that:
       - dispatches on `pr view --json <field> -q .<field>` and echoes the
         right value (baseRefName, headRefName, title, body, mergeCommit.oid)
       - dispatches on `pr merge ... --squash` and exits `merge_exit`
       - appends every invocation to `call_log` (one JSON line per call)
    """
    # The PR body/title may contain newlines; write each to a sidecar file the
    # shim `cat`s, so shell escaping never mangles the embedded newlines.
    body_file = os.path.join(shim_dir, "pr-body.txt")
    with open(body_file, "w") as bf:
        bf.write(pr_body)
    title_file = os.path.join(shim_dir, "pr-title.txt")
    with open(title_file, "w") as tf:
        tf.write(pr_title)
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
        f.write(f'TITLE_FILE={title_file!r}\n')
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
        f.write('    .title) cat "$TITLE_FILE" ;;\n')
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
              pr_body="", pr_title="", merge_sha="abc1234",
              item_status_exit=0, item_status_stderr="",
              integration_target=None):
    """Build a sandbox: a bin/ dir on PATH with the gh shim, and a
    script-dir holding the real merge-prs.py copy (via env override) plus a
    safety-check.py shim, plus an item-status.py shim in a separate
    rabbit-issue scripts dir (via env override). Return
    (cwd=tmpdir, env, call_log_path, item_status_log_path).

    `integration_target` (Inv 61): when None the env var is cleared so the
    script resolves the coexistence default (`dev`); set it to 'dev'/'main'
    to drive the resolved integration target."""
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
                   pr_body=pr_body, pr_title=pr_title, merge_sha=merge_sha)
    _write_safety_shim(script_dir, exit_code=safety_exit,
                       stderr_msg=safety_stderr)
    _write_item_status_shim(issue_dir, item_status_log,
                            exit_code=item_status_exit,
                            stderr_msg=item_status_stderr)

    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_ISSUE_SCRIPT_DIR"] = issue_dir
    env.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
    if integration_target is not None:
        env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = integration_target
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
# Skip-on-base-not-accepted (Inv 61): gh shim returns a base that is NEITHER
# dev NOR main (e.g. release/x). During the dev<->main coexistence window
# both dev and main are accepted; any other base is refused.
# Expected: status=skipped, reason=base-not-accepted. `gh pr merge` MUST NOT
# appear in the call log (refusal invariant).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="release/x")
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
            if r.get("reason") != "base-not-accepted":
                fail(f"skip-base: reason {r.get('reason')!r} != "
                     f"'base-not-accepted'")
            else:
                ok("skip-base: returns skipped/base-not-accepted")
    calls = _gh_calls(call_log)
    if any("pr merge" in c for c in calls):
        fail(f"skip-base: gh pr merge was called; calls={calls!r}")
    else:
        ok("skip-base: gh pr merge was NOT called (refusal invariant)")


# ---------------------------------------------------------------------------
# Coexistence (Inv 61) — target=dev (default): a dev-based PR is ACCEPTED and
# the manual close-after-merge STILL runs (target dev is not the default
# branch, so GitHub's native auto-close does not fire).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_body="Closes #501\n", merge_sha="dev9999",
        integration_target="dev",
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"coexist-dev: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"coexist-dev: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"coexist-dev: status {r.get('status')!r} != 'merged'")
        elif r.get("closed_issues", []) != [501]:
            fail(f"coexist-dev: closed_issues {r.get('closed_issues')!r} "
                 f"!= [501] (manual close MUST run while target=dev)")
        else:
            ok("coexist-dev: dev base merged AND manual close ran")
    if not _item_status_calls(item_status_log):
        fail("coexist-dev: item-status.py NOT invoked (manual close must run "
             "while target=dev)")
    else:
        ok("coexist-dev: item-status.py invoked (manual close)")


# ---------------------------------------------------------------------------
# Coexistence (Inv 61) — target=main: a main-based PR is ACCEPTED and the
# manual close-after-merge is SKIPPED (main IS the default branch, so
# GitHub's native keyword auto-close fires; the manual close is redundant).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body="Closes #502\n", merge_sha="main9999",
        integration_target="main",
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"coexist-main: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"coexist-main: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"coexist-main: status {r.get('status')!r} != 'merged' "
                 f"(main base must be accepted under coexistence)")
        elif r.get("closed_issues", []) != []:
            fail(f"coexist-main: closed_issues {r.get('closed_issues')!r} "
                 f"!= [] (manual close MUST be skipped when target=main; "
                 f"native auto-close fires)")
        else:
            ok("coexist-main: main base merged AND manual close skipped")
    calls = _gh_calls(call_log)
    if not any("pr merge" in c for c in calls):
        fail(f"coexist-main: gh pr merge was NOT called; calls={calls!r}")
    else:
        ok("coexist-main: gh pr merge was called for the main-based PR")
    if _item_status_calls(item_status_log):
        fail("coexist-main: item-status.py invoked (manual close must be "
             "skipped when target=main; GitHub closes natively)")
    else:
        ok("coexist-main: item-status.py NOT invoked (native auto-close)")


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
        # Issue #423 Part C: item-status.py close --reason completed now
        # REQUIRES --commit-sha <merge-sha>. merge-prs.py MUST pass it.
        if "--commit-sha" not in parts:
            fail(f"close-after-merge: call missing --commit-sha (issue "
                 f"#423): {c!r}")
        elif parts[parts.index("--commit-sha") + 1] != "deadbee":
            fail(f"close-after-merge: --commit-sha "
                 f"{parts[parts.index('--commit-sha') + 1]!r} != 'deadbee': "
                 f"{c!r}")
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
        item_status_exit=1, item_status_stderr="item-status failure\n",
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
# merge itself did not succeed (e.g. a base outside the accepted {dev, main}
# coexistence set).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="release/x", pr_body="Fixes #5\n",
    )
    _run(cwd, env, "42")
    if _item_status_calls(item_status_log):
        fail("close-skip: item-status.py invoked for a non-merged PR")
    else:
        ok("close-skip: item-status.py NOT invoked when merge was skipped")


# ===========================================================================
# Issue #499 — `--record-pending` appends merged PR numbers to
# pending_post_merge in the state file (read by run-post-merge.py). Without
# the flag, no state write occurs.
# ===========================================================================

def _state_path(state_dir):
    return os.path.join(state_dir, "auto-evolve-state.json")


def _seed_state(state_dir, pending=None, dispatch_journal=None):
    state = {
        "schema_version": "1.4.0",
        "updated_at": "2026-06-03T00:00:00Z",
        "queue": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
    }
    if pending is not None:
        state["pending_post_merge"] = pending
    if dispatch_journal is not None:
        state["dispatch_journal"] = dispatch_journal
    with open(_state_path(state_dir), "w") as f:
        json.dump(state, f)


# --- (A) --record-pending appends merged PRs to pending_post_merge ---------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="dev",
                                                    safety_exit=0, merge_exit=0)
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, pending=[])
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    proc = _run(cwd, env, "1,2,3", "--record-pending")
    if proc.returncode != 0:
        fail(f"record-pending: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("record-pending: exit 0")
    # stdout result array is unchanged (per-PR rows still emitted).
    try:
        results = json.loads(proc.stdout)
        if [r.get("status") for r in results] == ["merged", "merged", "merged"]:
            ok("record-pending: per-PR result array unchanged (3 merged)")
        else:
            fail(f"record-pending: unexpected result array {results!r}")
    except json.JSONDecodeError as e:
        fail(f"record-pending: stdout not JSON: {e}; stdout={proc.stdout!r}")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if sorted(state.get("pending_post_merge", [])) != [1, 2, 3]:
        fail(f"record-pending: pending_post_merge "
             f"{state.get('pending_post_merge')!r} != [1, 2, 3]")
    else:
        ok("record-pending: merged PRs appended to pending_post_merge")


# --- (B) --record-pending de-duplicates against existing pending -----------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="dev",
                                                    safety_exit=0, merge_exit=0)
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, pending=[2])
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    _run(cwd, env, "2,3", "--record-pending")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if sorted(state.get("pending_post_merge", [])) != [2, 3]:
        fail(f"record-pending-dedup: pending_post_merge "
             f"{state.get('pending_post_merge')!r} != [2, 3] (dedup failed)")
    else:
        ok("record-pending-dedup: existing PR not duplicated")


# --- (C) skipped/failed PRs are NOT recorded -------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="release/x")
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, pending=[])
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    _run(cwd, env, "42", "--record-pending")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if state.get("pending_post_merge", []) != []:
        fail(f"record-pending-skip: a skipped PR was recorded; "
             f"pending_post_merge={state.get('pending_post_merge')!r}")
    else:
        ok("record-pending-skip: skipped PR NOT recorded")


# --- (D) WITHOUT --record-pending, no state write occurs -------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="dev",
                                                    safety_exit=0, merge_exit=0)
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    # intentionally do NOT seed a state file
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    _run(cwd, env, "1,2", )
    if os.path.exists(_state_path(state_dir)):
        fail("no-record: state file written without --record-pending")
    else:
        ok("no-record: no state write without --record-pending")


# ===========================================================================
# Issue #564 — `--record-pending` also writes `last_merged_sha` to the
# on-disk state. No phase script previously persisted this field, so it
# lagged perpetually; phase-10's deterministic re-read (update-state.py)
# then captures it. The merge commit SHA is the one the gh shim returns via
# `gh pr view <#> --json mergeCommit -q .mergeCommit.oid`.
# ===========================================================================

# --- (E) last_merged_sha is set to the merge commit SHA after a merge ------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        merge_sha="cafe123",
    )
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, pending=[])
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    proc = _run(cwd, env, "42", "--record-pending")
    if proc.returncode != 0:
        fail(f"last-merged-sha: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if state.get("last_merged_sha") != "cafe123":
        fail(f"last-merged-sha: last_merged_sha "
             f"{state.get('last_merged_sha')!r} != 'cafe123' (issue #564)")
    else:
        ok("last-merged-sha: state.last_merged_sha == merge commit SHA")


# --- (F) last_merged_sha lands for a multi-PR run --------------------------
# The gh shim returns one fixed merge_sha for every PR; a multi-PR run still
# ends with that real SHA in last_merged_sha (not the seeded null).
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        merge_sha="beef456",
    )
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, pending=[])
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    _run(cwd, env, "1,2,3", "--record-pending")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if state.get("last_merged_sha") != "beef456":
        fail(f"last-merged-sha-multi: last_merged_sha "
             f"{state.get('last_merged_sha')!r} != 'beef456' (issue #564)")
    else:
        ok("last-merged-sha-multi: state.last_merged_sha set after multi-PR run")


# --- (G) no merged PR → last_merged_sha is left untouched ------------------
# base outside {dev, main} → the only PR is skipped; the seeded
# last_merged_sha must NOT be overwritten (no merge happened, so there is no
# merge SHA to record).
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="release/x")
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, pending=[])
    with open(_state_path(state_dir)) as f:
        s = json.load(f)
    s["last_merged_sha"] = "prior999"
    with open(_state_path(state_dir), "w") as f:
        json.dump(s, f)
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    _run(cwd, env, "42", "--record-pending")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if state.get("last_merged_sha") != "prior999":
        fail(f"last-merged-sha-skip: a skipped PR overwrote last_merged_sha "
             f"to {state.get('last_merged_sha')!r} (should stay 'prior999')")
    else:
        ok("last-merged-sha-skip: no merge → last_merged_sha preserved")


# ===========================================================================
# Issue #802 — fetch-before-close. `gh pr merge --squash` creates the squash
# commit on the REMOTE dev only; the local repo has not seen that SHA yet, so
# item-status.py (which requires --commit-sha to resolve to a real LOCAL
# commit, #423 Part C) rejects the close. BEFORE the close calls, merge-prs.py
# must run `git fetch origin <sha>` (falling back to `git fetch origin dev`)
# to make the merge SHA resolvable locally — NEVER `git merge`.
# ===========================================================================

def _write_git_shim(shim_dir, call_log, fetch_marker):
    """Write a `git` shim that records every invocation argv into `call_log`
    (one line per call). On a `fetch` subcommand it `touch`es `fetch_marker`
    (simulating the SHA becoming locally resolvable) and exits 0. Every other
    git subcommand exits 0 (no-op)."""
    shim = os.path.join(shim_dir, "git")
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        f.write(f'printf "%s\\n" "$*" >> {call_log!r}\n')
        f.write('if [ "$1" = "fetch" ]; then\n')
        f.write(f'  : > {fetch_marker!r}\n')
        f.write('fi\n')
        f.write('exit 0\n')
    os.chmod(shim, stat.S_IRWXU)


def _write_sha_gated_item_status_shim(shim_dir, call_log, fetch_marker):
    """Write an `item-status.py` shim that simulates the #423 Part C local-SHA
    requirement: the close FAILS (exit 1) unless `fetch_marker` exists,
    standing in for 'the --commit-sha does not resolve to a local commit'. Once
    the git-fetch shim has created the marker, the close succeeds. Records
    every invocation argv into `call_log`."""
    shim = os.path.join(shim_dir, "item-status.py")
    with open(shim, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import os, sys\n")
        f.write(f"with open({call_log!r}, 'a') as _f:\n")
        f.write("    _f.write(' '.join(sys.argv[1:]) + '\\n')\n")
        f.write(f"if not os.path.exists({fetch_marker!r}):\n")
        f.write("    sys.stderr.write('rabbit-issue: --commit-sha does not "
                "resolve to a commit in the local git repo\\n')\n")
        f.write("    sys.exit(1)\n")
        f.write("sys.exit(0)\n")
    os.chmod(shim, stat.S_IRWXU)


# --- (H) SHA not local at close time → git fetch lands it, close succeeds ---
with tempfile.TemporaryDirectory() as td:
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir)
    script_dir = os.path.join(td, "scripts")
    os.makedirs(script_dir)
    issue_dir = os.path.join(td, "issue-scripts")
    os.makedirs(issue_dir)
    gh_call_log = os.path.join(td, "gh-calls.log")
    open(gh_call_log, "w").close()
    git_call_log = os.path.join(td, "git-calls.log")
    open(git_call_log, "w").close()
    is_call_log = os.path.join(td, "item-status-calls.log")
    open(is_call_log, "w").close()
    fetch_marker = os.path.join(td, "sha-fetched.marker")

    _write_gh_shim(bin_dir, gh_call_log, base_ref="dev", merge_exit=0,
                   pr_body="Fixes #802\n", merge_sha="squash99")
    _write_safety_shim(script_dir, exit_code=0)
    _write_git_shim(bin_dir, git_call_log, fetch_marker)
    _write_sha_gated_item_status_shim(issue_dir, is_call_log, fetch_marker)

    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_ISSUE_SCRIPT_DIR"] = issue_dir
    proc = _run(td, env, "42")

    if proc.returncode != 0:
        fail(f"fetch-before-close: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"fetch-before-close: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None

    git_calls = _gh_calls(git_call_log)
    fetch_calls = [c for c in git_calls if c.startswith("fetch")]
    if not fetch_calls:
        fail(f"fetch-before-close: git fetch was NOT called before close; "
             f"git_calls={git_calls!r}")
    else:
        ok("fetch-before-close: git fetch invoked")
    # The fetch must target the merge SHA (preferred) — assert the SHA appears
    # in at least one fetch invocation.
    if fetch_calls and not any("squash99" in c for c in fetch_calls):
        fail(f"fetch-before-close: no fetch targeted the merge SHA 'squash99'; "
             f"fetch_calls={fetch_calls!r}")
    elif fetch_calls:
        ok("fetch-before-close: a git fetch targeted the merge SHA")
    # NEVER `git merge` (permission-denied in the loop environment).
    if any(c.startswith("merge") for c in git_calls):
        fail(f"fetch-before-close: git merge was called (forbidden); "
             f"git_calls={git_calls!r}")
    else:
        ok("fetch-before-close: git merge NOT called")

    # Ordering: the fetch must precede the FIRST item-status close. The marker
    # exists only after fetch, and the gated shim succeeds only when the marker
    # exists — so a successful close proves fetch-then-close ordering.
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"fetch-before-close: status {r.get('status')!r} != 'merged'")
        if r.get("closed_issues", []) != [802]:
            fail(f"fetch-before-close: closed_issues "
                 f"{r.get('closed_issues')!r} != [802] (close should now "
                 f"succeed because the SHA was fetched first)")
        else:
            ok("fetch-before-close: issue 802 closed after the SHA was fetched")
        if r.get("close_failed", []):
            fail(f"fetch-before-close: close_failed non-empty "
                 f"{r.get('close_failed')!r} (the fetch should have made the "
                 f"close succeed)")


# ===========================================================================
# Issue #838 — `--record-pending` promotes a merged PR's journal entry to
# `completed` (Inv 54) in the SAME read-modify-write that appends to
# pending_post_merge. Every issue the PR closes (parsed Closes/Fixes/Resolves)
# whose journal entry exists is marked `completed` with its `pr` recorded.
# ===========================================================================

# --- (I) a merge marks the closed issue's journal entry completed -----------
with tempfile.TemporaryDirectory() as td:
    body = "Fixes #815\n"
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_body=body, merge_sha="deadbee",
    )
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    journal = {"tick-1": {"started_at": "2026-06-04T12:00:00Z", "entries": [
        {"issue": 815, "feature": "rabbit-housekeep",
         "shape": "parallel-per-feature", "branch": "feat/815-x",
         "worktree": None, "pr": None, "status": "dispatched"},
        {"issue": 999, "feature": "other", "shape": "parallel-per-feature",
         "branch": None, "worktree": None, "pr": None, "status": "dispatched"},
    ]}}
    _seed_state(state_dir, pending=[], dispatch_journal=journal)
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    proc = _run(cwd, env, "820", "--record-pending")
    if proc.returncode != 0:
        fail(f"journal-complete: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    entries = {e["issue"]: e
               for e in state["dispatch_journal"]["tick-1"]["entries"]}
    if entries[815].get("status") != "completed":
        fail(f"journal-complete: issue 815 entry status "
             f"{entries[815].get('status')!r} != 'completed'")
    elif entries[815].get("pr") != 820:
        fail(f"journal-complete: issue 815 entry pr "
             f"{entries[815].get('pr')!r} != 820")
    elif entries[999].get("status") != "dispatched":
        fail(f"journal-complete: unrelated issue 999 was wrongly mutated to "
             f"{entries[999].get('status')!r}")
    else:
        ok("journal-complete: merge marks the closed issue's entry completed")


# ===========================================================================
# Issue #868 — close-ref in the PR TITLE (not just the body).
# PRs merge into `dev`, not the default branch, so GitHub's native auto-close
# never fires; the loop's explicit close depends entirely on merge-prs.py's
# close-ref parsing. That parsing previously scanned the PR BODY only, so a
# subagent that put `Closes #N` in the TITLE alone merged the PR but left the
# issue OPEN (a silent convergence hole — observed: PR #865 left #862 open).
# merge-prs.py MUST now scan BOTH the title AND the body, unioning the
# referenced issue numbers (deduplicated).
# ===========================================================================

# ---------------------------------------------------------------------------
# Title-only close: the close-ref lives in the PR TITLE, the body has none.
# Expected: the referenced issue is closed (RED before #868, GREEN after).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_title="fix(loop): patch the hole (closes #862)",
        pr_body="A change with no close-ref in the body.\n",
        merge_sha="title99",
    )
    proc = _run(cwd, env, "865")
    if proc.returncode != 0:
        fail(f"title-only-close: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"title-only-close: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"title-only-close: status {r.get('status')!r} != 'merged'")
        if r.get("closed_issues", []) != [862]:
            fail(f"title-only-close: closed_issues {r.get('closed_issues')!r} "
                 f"!= [862] (a TITLE-only close-ref must now close the issue)")
        else:
            ok("title-only-close: TITLE-only close-ref closes issue 862")
    is_calls = _item_status_calls(item_status_log)
    closed_nums = {c.split()[1] for c in is_calls if c.split()[:1] == ["close"]}
    if closed_nums != {"862"}:
        fail(f"title-only-close: item-status closed {closed_nums!r} != {{862}}")
    else:
        ok("title-only-close: item-status.py close invoked for 862")


# ---------------------------------------------------------------------------
# Body-only close STILL works (backward-compatibility): close-ref in the body,
# title carries no ref. The existing behavior must be preserved.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_title="fix(loop): a plain title with no close-ref",
        pr_body="Some change.\n\nCloses #770\n",
        merge_sha="body99",
    )
    proc = _run(cwd, env, "771")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"body-only-close: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("closed_issues", []) != [770]:
            fail(f"body-only-close: closed_issues "
                 f"{results[0].get('closed_issues')!r} != [770]")
        else:
            ok("body-only-close: BODY-only close-ref still closes issue 770")
    is_calls = _item_status_calls(item_status_log)
    closed_nums = {c.split()[1] for c in is_calls if c.split()[:1] == ["close"]}
    if closed_nums != {"770"}:
        fail(f"body-only-close: item-status closed {closed_nums!r} != {{770}}")
    else:
        ok("body-only-close: item-status.py close invoked for 770")


# ---------------------------------------------------------------------------
# Title AND body both reference issues, with one shared issue. Expected: the
# UNION of distinct issue numbers is closed, and the shared issue is closed
# exactly ONCE (dedup across the two locations).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_title="feat: do the thing (Closes #100, fixes #200)",
        pr_body="Detail.\n\nCloses #200\nResolves #300\n",
        merge_sha="union99",
    )
    proc = _run(cwd, env, "999")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"union-close: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        if sorted(results[0].get("closed_issues", [])) != [100, 200, 300]:
            fail(f"union-close: closed_issues "
                 f"{results[0].get('closed_issues')!r} != [100, 200, 300]")
        else:
            ok("union-close: title+body union closes 100/200/300")
    is_calls = [c for c in _item_status_calls(item_status_log)
                if c.split()[:1] == ["close"]]
    closed_list = [c.split()[1] for c in is_calls]
    if sorted(closed_list) != ["100", "200", "300"]:
        fail(f"union-close: item-status close targets {sorted(closed_list)!r} "
             f"!= ['100', '200', '300']")
    elif closed_list.count("200") != 1:
        fail(f"union-close: shared issue 200 closed "
             f"{closed_list.count('200')} times (must dedup to 1): "
             f"{closed_list!r}")
    else:
        ok("union-close: shared issue 200 closed exactly once (dedup)")


sys.exit(FAIL)
