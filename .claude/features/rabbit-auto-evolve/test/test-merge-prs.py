#!/usr/bin/env python3
"""test-merge-prs.py — e2e tests for scripts/merge-prs.py (Inv 6 / Inv 61).

The dev->main coexistence window has CLOSED: `main` is the sole accepted
integration target. Every accepted base is the default branch, so GitHub's
native `Fixes/Closes/Resolves` keyword auto-close ALWAYS fires and the manual
close-after-merge path has been RETIRED. merge-prs.py no longer invokes
item-status.py and no longer git-fetches the merge SHA to make a manual close
resolvable.

Covers the spec'd surface of `scripts/merge-prs.py`:
  - --help smoke
  - skip-on-base-not-accepted: a `dev` base (and any non-main base) is REFUSED
    (defense-in-depth above safety-check.py)
  - skip-on-safety-fail
  - happy path → status: merged, with `--admin` (main is branch-protected)
  - refusal invariant: `gh pr merge` is NEVER called when base != main
  - the manual close path is GONE: item-status.py is NEVER invoked
  - journal promotion still works, deriving its closed-issue set from the PR's
    parsed close-refs (title + body) — the same set GitHub auto-closes natively
  - close-refs are still parsed (title + body union) into `closed_issues`

Fixtures use a tempdir on PATH carrying:
  - a `gh` shim that dispatches on the subcommand (pr view / pr merge) and
    records every invocation into a call log
  - a `safety-check.py` shim that exits 0 by default (overrideable to non-zero)
  - an `item-status.py` shim (in a separate rabbit-issue scripts dir) whose
    call log proves the RETIRED manual-close path is never invoked

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


def _write_gh_shim(shim_dir, call_log, base_ref="main", head_ref="feat/x",
                   merge_exit=0, merge_stderr="", pr_body="", pr_title="",
                   merge_sha="abc1234", open_issues=None, auto_close_map=None,
                   pr_bodies=None):
    """Write a `gh` shim that:
       - dispatches on `pr view <N> --json <field> -q .<field>` and echoes the
         right value (baseRefName, headRefName, title, body, mergeCommit.oid)
       - dispatches on `pr merge ... --squash` and exits `merge_exit`
       - dispatches on `issue view <N> --json state -q .state` and echoes
         `OPEN` when N is in `open_issues` (and not auto-closed by a prior
         merge), else `CLOSED` (issue #1101: the close-ref open-issue
         cross-check guard). `open_issues` is an iterable of int issue numbers
         treated as currently-open; when None NO issue is open, so every parsed
         close-ref is dropped (the strictest case).
       - appends every invocation to `call_log` (one JSON line per call)

    Issue #1109 — `auto_close_map` simulates GitHub's server-side keyword
    auto-close: a dict {pr_number: [issue, ...]} of the issues that flip from
    OPEN to CLOSED *when that PR merges*. On `pr merge <N>`, the shim appends
    `auto_close_map[N]` to a persistent closed-marker file; a subsequent
    `issue view` for a marked issue returns CLOSED even though it is in
    `open_issues`. This lets a test distinguish a PRE-merge open snapshot from a
    POST-merge query: the genuine target is OPEN before its own merge and CLOSED
    after. An issue auto-closes ONLY when ITS OWN PR merges (per-PR fidelity in
    a batch), exactly as GitHub does.

    `pr_bodies` is an optional dict {pr_number: body} for per-PR distinct
    bodies (a batch where each PR closes its OWN target). When a viewed PR is
    absent from `pr_bodies` the shim falls back to the single `pr_body`."""
    # The PR body/title may contain newlines; write each to a sidecar file the
    # shim `cat`s, so shell escaping never mangles the embedded newlines.
    body_file = os.path.join(shim_dir, "pr-body.txt")
    with open(body_file, "w") as bf:
        bf.write(pr_body)
    title_file = os.path.join(shim_dir, "pr-title.txt")
    with open(title_file, "w") as tf:
        tf.write(pr_title)
    # Per-PR body sidecars (issue #1109 batch fidelity): pr-body-<N>.txt.
    for pr_num, body in (pr_bodies or {}).items():
        with open(os.path.join(shim_dir, f"pr-body-{int(pr_num)}.txt"),
                  "w") as pf:
            pf.write(body)
    # Space-delimited set of open issue numbers the shim recognizes; the
    # `issue view` dispatch echoes OPEN for a member, CLOSED otherwise.
    open_set = " ".join(str(int(n)) for n in (open_issues or []))
    # The persistent closed-marker the merge writes to (auto-close simulation).
    closed_marker = os.path.join(shim_dir, "auto-closed.txt")
    # Per-PR auto-close lists, written to a sidecar file as `<pr>:<sp-joined-
    # issues>` lines (a file, not an env string, so embedded newlines survive).
    auto_close_file = os.path.join(shim_dir, "auto-close-spec.txt")
    with open(auto_close_file, "w") as acf:
        for pr_num, issues in (auto_close_map or {}).items():
            acf.write(
                f"{int(pr_num)}:" + " ".join(str(int(i)) for i in issues)
                + "\n")
    shim = os.path.join(shim_dir, "gh")
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        # Record the call: just the argv joined by ASCII-unit-separator-ish.
        f.write(f'CALL_LOG="{call_log}"\n')
        f.write('printf "%s\\n" "$*" >> "$CALL_LOG"\n')
        f.write(f'OPEN_SET={open_set!r}\n')
        f.write(f'BASE_REF={base_ref}\n')
        f.write(f'HEAD_REF={head_ref}\n')
        f.write(f'MERGE_EXIT={merge_exit}\n')
        f.write(f'MERGE_STDERR={merge_stderr!r}\n')
        f.write(f'BODY_FILE={body_file!r}\n')
        f.write(f'TITLE_FILE={title_file!r}\n')
        f.write(f'MERGE_SHA={merge_sha!r}\n')
        f.write(f'SHIM_DIR={shim_dir!r}\n')
        f.write(f'CLOSED_MARKER={closed_marker!r}\n')
        f.write(f'AUTO_CLOSE_FILE={auto_close_file!r}\n')
        # Walk args. First arg is subcommand `pr`, second is the action.
        f.write('SUB="$1"; shift\n')
        f.write('ACTION="$1"; shift\n')
        f.write('if [ "$SUB" = "pr" ] && [ "$ACTION" = "view" ]; then\n')
        # The viewed PR number is the first remaining positional arg.
        f.write('  PRNUM="$1"\n')
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
        # Per-PR body sidecar wins over the shared body, when present.
        f.write('  PR_BODY_FILE="$SHIM_DIR/pr-body-$PRNUM.txt"\n')
        f.write('  if [ ! -f "$PR_BODY_FILE" ]; then PR_BODY_FILE="$BODY_FILE"; fi\n')
        f.write('  case "$QUERY" in\n')
        f.write('    .baseRefName) printf "%s\\n" "$BASE_REF" ;;\n')
        f.write('    .headRefName) printf "%s\\n" "$HEAD_REF" ;;\n')
        f.write('    .title) cat "$TITLE_FILE" ;;\n')
        f.write('    .body) cat "$PR_BODY_FILE" ;;\n')
        f.write('    .mergeCommit.oid) printf "%s\\n" "$MERGE_SHA" ;;\n')
        f.write('    *) printf "{}\\n" ;;\n')
        f.write('  esac\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        # issue view <N> --json state -q .state → OPEN if N in OPEN_SET AND
        # not already auto-closed by a prior merge (issue #1109).
        f.write('if [ "$SUB" = "issue" ] && [ "$ACTION" = "view" ]; then\n')
        f.write('  N="$1"\n')
        f.write('  STATE=CLOSED\n')
        f.write('  for o in $OPEN_SET; do\n')
        f.write('    if [ "$o" = "$N" ]; then STATE=OPEN; fi\n')
        f.write('  done\n')
        # If a prior merge auto-closed N, it is now CLOSED (post-merge query).
        f.write('  if [ -f "$CLOSED_MARKER" ]; then\n')
        f.write('    for c in $(cat "$CLOSED_MARKER"); do\n')
        f.write('      if [ "$c" = "$N" ]; then STATE=CLOSED; fi\n')
        f.write('    done\n')
        f.write('  fi\n')
        f.write('  printf "%s\\n" "$STATE"\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('if [ "$SUB" = "pr" ] && [ "$ACTION" = "merge" ]; then\n')
        # The merged PR number is the first remaining positional arg.
        f.write('  PRNUM="$1"\n')
        f.write('  if [ "$MERGE_EXIT" = "0" ] && [ -f "$AUTO_CLOSE_FILE" ]; then\n')
        # Append this PR\'s auto-close issues to the persistent marker (GitHub\'s
        # server-side keyword auto-close fires on merge, issue #1109).
        f.write('    while IFS=: read pr issues; do\n')
        f.write('      if [ "$pr" = "$PRNUM" ]; then\n')
        f.write('        for i in $issues; do printf "%s\\n" "$i" >> "$CLOSED_MARKER"; done\n')
        f.write('      fi\n')
        f.write('    done < "$AUTO_CLOSE_FILE"\n')
        f.write('  fi\n')
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
    Records every invocation argv into `call_log` (one line per call).

    The manual close-after-merge path has been RETIRED, so merge-prs.py must
    NEVER invoke this shim; its call log is asserted EMPTY in every case.
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


def _make_env(tmpdir, base_ref="main", head_ref="feat/x",
              merge_exit=0, merge_stderr="",
              safety_exit=0, safety_stderr="",
              pr_body="", pr_title="", merge_sha="abc1234",
              item_status_exit=0, item_status_stderr="",
              open_issues=None, auto_close_map=None, pr_bodies=None):
    """Build a sandbox: a bin/ dir on PATH with the gh shim, and a
    script-dir holding the real merge-prs.py copy (via env override) plus a
    safety-check.py shim, plus an item-status.py shim in a separate
    rabbit-issue scripts dir (via env override). Return
    (cwd=tmpdir, env, call_log_path, item_status_log_path).

    Inv 61: `main` is the sole accepted integration target; the
    RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET env var has been removed and is
    cleared here for hygiene (it has no effect)."""
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
                   pr_body=pr_body, pr_title=pr_title, merge_sha=merge_sha,
                   open_issues=open_issues, auto_close_map=auto_close_map,
                   pr_bodies=pr_bodies)
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
# Skip-on-base-not-accepted (Inv 61): gh shim returns a base that is NOT the
# sole accepted target `main` (e.g. release/x). Any non-main base is refused.
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
# Post-teardown (Inv 61): a `dev` base is now REFUSED — the coexistence window
# has closed, so `dev` is no longer an accepted integration target. Expected:
# status=skipped, reason=base-not-accepted; `gh pr merge` MUST NOT be called.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="dev", safety_exit=0, merge_exit=0,
        pr_body="Closes #501\n", merge_sha="dev9999",
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"dev-rejected: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"dev-rejected: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "skipped":
            fail(f"dev-rejected: status {r.get('status')!r} != 'skipped' "
                 f"(dev is no longer accepted post-teardown)")
        elif r.get("reason") != "base-not-accepted":
            fail(f"dev-rejected: reason {r.get('reason')!r} != "
                 f"'base-not-accepted'")
        else:
            ok("dev-rejected: dev base refused with base-not-accepted")
    calls = _gh_calls(call_log)
    if any("pr merge" in c for c in calls):
        fail(f"dev-rejected: gh pr merge was called for a dev base; "
             f"calls={calls!r}")
    else:
        ok("dev-rejected: gh pr merge was NOT called for the dev base")
    if _item_status_calls(item_status_log):
        fail("dev-rejected: item-status.py invoked (manual close path is "
             "retired and the dev base was refused anyway)")
    else:
        ok("dev-rejected: item-status.py NOT invoked")


# ---------------------------------------------------------------------------
# Main base (Inv 61): a main-based PR is ACCEPTED and merged. The manual
# close-after-merge path is RETIRED — item-status.py is NEVER invoked; GitHub's
# native keyword auto-close handles issue closure. The merged result row still
# carries the PR's parsed close-refs under `closed_issues` (the set GitHub
# auto-closes, used by journal promotion).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body="Closes #502\n", merge_sha="main9999",
        open_issues=[502],
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"main-merge: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"main-merge: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"main-merge: status {r.get('status')!r} != 'merged' "
                 f"(main base must be accepted)")
        elif r.get("closed_issues", []) != [502]:
            fail(f"main-merge: closed_issues {r.get('closed_issues')!r} "
                 f"!= [502] (the parsed close-refs feed journal promotion)")
        else:
            ok("main-merge: main base merged; closed_issues from close-refs")
    calls = _gh_calls(call_log)
    if not any("pr merge" in c for c in calls):
        fail(f"main-merge: gh pr merge was NOT called; calls={calls!r}")
    else:
        ok("main-merge: gh pr merge was called for the main-based PR")
    if _item_status_calls(item_status_log):
        fail("main-merge: item-status.py invoked (manual close path is "
             "RETIRED; GitHub closes natively)")
    else:
        ok("main-merge: item-status.py NOT invoked (native auto-close)")


# ===========================================================================
# Issue #973 — admin-override merge into the protected default branch (main).
#
# `main` is branch-protected with required_approving_review_count: 1
# (enforce_admins: false), so a plain `gh pr merge --squash` is BLOCKED — the
# bot cannot approve its own PR. The fix: every merge (every accepted base is
# now `main`, the default branch) uses `gh pr merge --squash --admin` to bypass
# ONLY the required-review the bot structurally cannot satisfy (the contract
# repo-gate, run PRE-merge, is the real quality gate and is unchanged).
# ===========================================================================

def _merge_calls(call_log):
    return [c for c in _gh_calls(call_log) if "pr merge" in c]


# --- (J) main-base merge uses --admin (admin-override past required review) --
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        merge_sha="main9999",
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"admin-main: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    merge_calls = _merge_calls(call_log)
    if not merge_calls:
        fail(f"admin-main: gh pr merge was NOT called; "
             f"calls={_gh_calls(call_log)!r}")
    elif not all("--admin" in c for c in merge_calls):
        fail(f"admin-main: main-base merge missing --admin (issue #973): "
             f"{merge_calls!r}")
    elif not all("--squash" in c for c in merge_calls):
        fail(f"admin-main: main-base merge missing --squash: {merge_calls!r}")
    else:
        ok("admin-main: main-base merge uses --squash --admin")


# ---------------------------------------------------------------------------
# Skip-on-safety-fail: gh shim returns base=main; safety-check.py shim
# exits non-zero. Expected: status=skipped, reason=safety-check-failed;
# `gh pr merge` MUST NOT appear in the call log.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=2,
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
# Happy path: gh shim returns base=main, safety-check shim exits 0,
# gh pr merge exits 0. Expected: status=merged; gh pr merge was called.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main",
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main",
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
# invocation recorded in the gh call log does NOT contain `--auto`.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main",
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main",
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
# Native auto-close + close-ref parsing.
#
# Every accepted base is `main` (the default branch), so GitHub's
# `Fixes/Closes/Resolves #N` keyword auto-close ALWAYS fires; the loop's
# manual close path is RETIRED. merge-prs.py no longer invokes item-status.py.
# It still PARSES the merged PR's close-refs (title + body union) into
# `closed_issues` so journal promotion can derive the set of issues the merge
# closed (native auto-close does not report the set back to the loop).
# ===========================================================================

# ---------------------------------------------------------------------------
# close-refs across the three accepted keywords (Fixes / Closes / Resolves),
# case-insensitively. Expected: status=merged; closed_issues is the sorted,
# deduplicated set; item-status.py is NEVER invoked (manual close retired).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    body = "Some change.\n\nFixes #11\nCloses #22\nresolves #33\n"
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body=body, merge_sha="deadbee", open_issues=[11, 22, 33],
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"close-refs: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"close-refs: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and isinstance(results, list) and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"close-refs: status {r.get('status')!r} != 'merged'")
        else:
            ok("close-refs: status merged")
        if sorted(r.get("closed_issues", [])) != [11, 22, 33]:
            fail(f"close-refs: closed_issues "
                 f"{r.get('closed_issues')!r} != [11, 22, 33]")
        else:
            ok("close-refs: closed_issues == [11, 22, 33]")
    elif results is not None:
        fail(f"close-refs: expected 1-element array, got {results!r}")

    if _item_status_calls(item_status_log):
        fail("close-refs: item-status.py invoked (manual close path is "
             "RETIRED; native auto-close handles closure)")
    else:
        ok("close-refs: item-status.py NOT invoked (native auto-close)")


# ---------------------------------------------------------------------------
# No references in body: item-status.py is NOT invoked; closed_issues empty.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
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
        fail("no-refs: item-status.py was invoked (manual close retired)")
    else:
        ok("no-refs: item-status.py NOT invoked")


# ---------------------------------------------------------------------------
# Refusal invariant for closed_issues: a skipped PR (base outside the accepted
# {main} set) carries no closed_issues and never invokes item-status.py.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="release/x", pr_body="Fixes #5\n",
    )
    proc = _run(cwd, env, "42")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("closed_issues"):
            fail(f"close-skip: skipped PR carries closed_issues "
                 f"{results[0].get('closed_issues')!r}")
        else:
            ok("close-skip: skipped PR carries no closed_issues")
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main",
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main",
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
    cwd, env, call_log, item_status_log = _make_env(td, base_ref="main",
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
        td, base_ref="main", safety_exit=0, merge_exit=0,
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
        td, base_ref="main", safety_exit=0, merge_exit=0,
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
# base outside {main} → the only PR is skipped; the seeded last_merged_sha must
# NOT be overwritten (no merge happened, so there is no merge SHA to record).
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
# Issue #838 — `--record-pending` promotes a merged PR's journal entry to
# `completed` (Inv 54) in the SAME read-modify-write that appends to
# pending_post_merge. The set of issues the PR closed is derived from its
# parsed close-refs (title + body) — the same set GitHub auto-closes natively.
# Every such issue whose journal entry exists is marked `completed` with its
# `pr` recorded.
# ===========================================================================

# --- (I) a merge marks the closed issue's journal entry completed -----------
with tempfile.TemporaryDirectory() as td:
    body = "Fixes #815\n"
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body=body, merge_sha="deadbee", open_issues=[815],
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
    if _item_status_calls(item_status_log):
        fail("journal-complete: item-status.py invoked (journal promotion must "
             "derive its set from close-refs, NOT a manual close)")
    else:
        ok("journal-complete: item-status.py NOT invoked (close-ref derived)")


# ===========================================================================
# Issue #868 — close-ref in the PR TITLE (not just the body).
# The loop derives the closed-issue set (for journal promotion) from the PR's
# close-refs. That parsing must scan BOTH the title AND the body, unioning the
# referenced issue numbers (deduplicated) — a subagent that put `Closes #N` in
# the title alone must still have #N recorded under closed_issues.
# ===========================================================================

# ---------------------------------------------------------------------------
# Title-only close-ref: the ref lives in the PR TITLE, the body has none.
# Expected: the referenced issue appears in closed_issues.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_title="fix(loop): patch the hole (closes #862)",
        pr_body="A change with no close-ref in the body.\n",
        merge_sha="title99", open_issues=[862],
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
                 f"!= [862] (a TITLE-only close-ref must be parsed)")
        else:
            ok("title-only-close: TITLE-only close-ref recorded for 862")
    if _item_status_calls(item_status_log):
        fail("title-only-close: item-status.py invoked (manual close retired)")
    else:
        ok("title-only-close: item-status.py NOT invoked")


# ---------------------------------------------------------------------------
# Body-only close-ref STILL works (backward-compatibility): ref in the body,
# title carries no ref.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_title="fix(loop): a plain title with no close-ref",
        pr_body="Some change.\n\nCloses #770\n",
        merge_sha="body99", open_issues=[770],
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
            ok("body-only-close: BODY-only close-ref recorded for 770")


# ---------------------------------------------------------------------------
# Title AND body both reference issues, with one shared issue. Expected: the
# UNION of distinct issue numbers, deduplicated (the shared issue appears once).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_title="feat: do the thing (Closes #100, fixes #200)",
        pr_body="Detail.\n\nCloses #200\nResolves #300\n",
        merge_sha="union99", open_issues=[100, 200, 300],
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
            ok("union-close: title+body union → 100/200/300 (deduplicated)")


# ===========================================================================
# Issue #1101 — close-ref open-issue cross-check guard.
#
# THE BUG: PR #1100's body enumerated its three fixes as "Fix #1 / Fix #2 /
# Fix #3" — GitHub's closing-keyword grammar treats `Fix #N` as a closing
# keyword, so the merge recorded closed_issues = [1, 2, 3, 1096]. It was
# harmless ONLY because #1/#2/#3 are ancient already-merged PRs; had they been
# OPEN issues the merge would have WRONGLY recorded (and the loop acted on)
# closing unrelated open issues — a silent convergence-guarantee violation.
#
# THE GUARD: merge-prs.py now cross-checks every parsed `#N` against
# `gh issue view N --json state -q .state` and keeps ONLY currently-OPEN
# issues in closed_issues. A `Fix #N` enumeration whose N is NOT an open issue
# (a PR number, an already-closed issue, a bare number) is DROPPED — logged to
# stderr, never recorded. The explicit `Closes #<open-target>` survives.
# ===========================================================================

# --- (K) the enumeration trap: "Fix #1 / Fix #2 / Fix #3" + "Closes #1096" --
# Only #1096 is an OPEN issue; #1/#2/#3 are not (they are old PRs). Expected:
# closed_issues == [1096] ONLY; #1/#2/#3 dropped (logged, not recorded).
with tempfile.TemporaryDirectory() as td:
    body = ("This PR makes three fixes:\n"
            "Fix #1 do the first thing\n"
            "Fix #2 do the second thing\n"
            "Fix #3 do the third thing\n\n"
            "Closes #1096\n")
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body=body, merge_sha="trap999", open_issues=[1096],
    )
    proc = _run(cwd, env, "1100")
    if proc.returncode != 0:
        fail(f"closeref-guard: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"closeref-guard: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"closeref-guard: status {r.get('status')!r} != 'merged'")
        if r.get("closed_issues", []) != [1096]:
            fail(f"closeref-guard: closed_issues {r.get('closed_issues')!r} "
                 f"!= [1096] — the Fix #1/#2/#3 enumeration MUST be dropped "
                 f"(only the OPEN target #1096 is recorded)")
        else:
            ok("closeref-guard: Fix #1/#2/#3 dropped; only OPEN #1096 recorded")


# --- (L) a real Closes #N for an OPEN N is recorded -------------------------
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body="Closes #777\n", merge_sha="open999", open_issues=[777],
    )
    proc = _run(cwd, env, "778")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"closeref-open: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("closed_issues", []) != [777]:
            fail(f"closeref-open: closed_issues "
                 f"{results[0].get('closed_issues')!r} != [777] (an OPEN "
                 f"Closes-target MUST be recorded)")
        else:
            ok("closeref-open: OPEN Closes-target #777 recorded")


# --- (M) a Closes #N where N is CLOSED/non-issue is dropped -----------------
# No issue is open (open_issues=None). Even an explicit `Closes #N` is dropped
# when N is not a currently-open issue — never silently "close" a closed/PR num.
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body="Closes #3\n", merge_sha="closed999",
    )
    proc = _run(cwd, env, "779")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"closeref-closed: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("closed_issues", []) != []:
            fail(f"closeref-closed: closed_issues "
                 f"{results[0].get('closed_issues')!r} != [] (a non-OPEN "
                 f"#N MUST be dropped)")
        else:
            ok("closeref-closed: non-OPEN #3 dropped from closed_issues")


# --- (N) mixed: title `Closes #500` (open) + body `Fix #2` (not open) -------
# Union across title+body, THEN filter to open. Expected: [500] only.
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_title="feat: thing (Closes #500)",
        pr_body="Detail.\nFix #2 some sub-task\n",
        merge_sha="mixed999", open_issues=[500],
    )
    proc = _run(cwd, env, "501")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"closeref-mixed: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("closed_issues", []) != [500]:
            fail(f"closeref-mixed: closed_issues "
                 f"{results[0].get('closed_issues')!r} != [500] (title OPEN "
                 f"#500 kept; body Fix #2 dropped)")
        else:
            ok("closeref-mixed: title OPEN #500 kept; body Fix #2 dropped")


# ===========================================================================
# Issue #1109 — the open-state cross-check must be a PRE-merge SNAPSHOT, not a
# POST-merge query.
#
# THE REGRESSION (introduced by #1101 / Inv 68): the cross-check ran AFTER
# `gh pr merge`. But the merge targets the default branch `main`, so GitHub's
# server-side keyword auto-close closes the genuine target ON merge. The
# post-merge `gh issue view` then sees the just-auto-closed genuine target as
# "not currently-open" and DROPS it — recording closed_issues=[] for a PR that
# legitimately closed an issue (observed: a 4-PR batch recorded [] for ALL).
#
# THE FIX: snapshot each PR's close-ref open-state BEFORE that PR's merge.
# Record the refs that were OPEN in the pre-merge snapshot (the genuine target,
# closed BY this merge), while still dropping a bare `Fix #N` enumeration whose
# N was NOT open pre-merge. Snapshot per-PR immediately before its own merge so
# a later PR in a batch is never judged against an issue an earlier PR closed.
# ===========================================================================

# --- (O) genuine target OPEN pre-merge, CLOSED by its own auto-close ---------
# `Closes #500`; #500 is OPEN in the pre-merge snapshot, then GitHub auto-closes
# it ON this PR's merge. The CURRENT (buggy) code queries post-merge, sees #500
# closed, and records []. The fix records [500].
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body="Closes #500\n", merge_sha="snap500",
        open_issues=[500], auto_close_map={42: [500]},
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"premerge-snapshot: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"premerge-snapshot: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        r = results[0]
        if r.get("status") != "merged":
            fail(f"premerge-snapshot: status {r.get('status')!r} != 'merged'")
        if r.get("closed_issues", []) != [500]:
            fail(f"premerge-snapshot: closed_issues {r.get('closed_issues')!r} "
                 f"!= [500] — a genuine target OPEN PRE-merge must be RECORDED "
                 f"even though GitHub auto-closes it ON merge (issue #1109)")
        else:
            ok("premerge-snapshot: OPEN-pre-merge target recorded despite "
               "post-merge auto-close")


# --- (P) enumeration NOT open pre-merge dropped; genuine target kept ---------
# `Fix #1 / Fix #2` (neither open pre-merge) + `Closes #500` (open pre-merge,
# auto-closed on merge). Records ONLY [500]; #1/#2 dropped.
with tempfile.TemporaryDirectory() as td:
    body = ("This PR makes sub-tasks:\n"
            "Fix #1 do the first thing\n"
            "Fix #2 do the second thing\n\n"
            "Closes #500\n")
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        pr_body=body, merge_sha="snapmix",
        open_issues=[500], auto_close_map={42: [500]},
    )
    proc = _run(cwd, env, "42")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"premerge-enum: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 1:
        if results[0].get("closed_issues", []) != [500]:
            fail(f"premerge-enum: closed_issues "
                 f"{results[0].get('closed_issues')!r} != [500] — the "
                 f"Fix #1/#2 enumeration (NOT open pre-merge) must be dropped, "
                 f"the OPEN-pre-merge target #500 kept (issue #1109)")
        else:
            ok("premerge-enum: Fix #1/#2 dropped; OPEN-pre-merge #500 kept")


# --- (Q) batch: each PR closes its own OWN open target -----------------------
# Two PRs, each closing its own target (#601 / #602), each auto-closed ON its
# own merge. Each result row records its OWN target. The pre-merge snapshot for
# PR2 must be taken BEFORE PR2's merge — PR1's earlier merge auto-closed #601,
# which must not affect PR2's judgment of its own (still-open-pre-merge) #602.
with tempfile.TemporaryDirectory() as td:
    cwd, env, call_log, item_status_log = _make_env(
        td, base_ref="main", safety_exit=0, merge_exit=0,
        merge_sha="batchsha",
        open_issues=[601, 602],
        auto_close_map={71: [601], 72: [602]},
        pr_bodies={71: "Closes #601\n", 72: "Closes #602\n"},
    )
    proc = _run(cwd, env, "71,72")
    if proc.returncode != 0:
        fail(f"premerge-batch: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"premerge-batch: stdout not JSON: {e}; stdout={proc.stdout!r}")
        results = None
    if results is not None and len(results) == 2:
        rows = {r.get("pr"): r for r in results}
        if rows.get(71, {}).get("closed_issues", []) != [601]:
            fail(f"premerge-batch: PR 71 closed_issues "
                 f"{rows.get(71, {}).get('closed_issues')!r} != [601]")
        elif rows.get(72, {}).get("closed_issues", []) != [602]:
            fail(f"premerge-batch: PR 72 closed_issues "
                 f"{rows.get(72, {}).get('closed_issues')!r} != [602] — PR2's "
                 f"pre-merge snapshot must be taken before PR2's own merge, "
                 f"unaffected by PR1's earlier auto-close (issue #1109)")
        else:
            ok("premerge-batch: each PR records its OWN pre-merge-open target")
    elif results is not None:
        fail(f"premerge-batch: expected 2 results, got {len(results)}")


sys.exit(FAIL)
