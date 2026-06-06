#!/usr/bin/env python3
"""test-resolve-duplicate.py — e2e tests for scripts/resolve-duplicate.py
(Inv 60, issue #943).

The duplicate-DETECTION heuristic stays in triage-issue.py (tested by
test-triage-rules.py). This script owns only RESOLUTION: recording the
AUTHORITATIVE GitHub-native duplicate state.

The script is invoked as a subprocess; a `gh` shim is placed on $PATH so no
real network call occurs. The shim LOGS every invocation to a file so the
test can assert the exact native PATCH (`state=closed`, `state_reason=duplicate`)
and the cross-reference comment were issued, and serves fixture JSON for the
`gh issue view` reads `status` performs.

Assertions:
  1. `resolve <dup> <canonical>` closes <dup> with the native
     `state_reason=duplicate` PATCH (NOT a reinvented `duplicate` label, NOT a
     not-planned close) and cross-links <canonical> via a comment.
  2. `status <n>` reports an issue closed with native `stateReason=duplicate`
     as a recognized duplicate (native state AUTHORITATIVE).
  3. `status <n>` honors a legacy `duplicate`-LABELLED issue as a recognized
     duplicate on read (deprecating coexistence mirror).
  4. `status <n>` reports an ordinary open issue (no native state, no label)
     as NOT a duplicate.
  5. `resolve` NEVER stamps the reinvented `duplicate` label.
  6. --help smoke test.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "resolve-duplicate.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_shim(shim_dir, view_responses):
    """Write a `gh` shim that logs every call and serves view fixtures.

    view_responses: dict issue-number-string -> JSON string emitted for the
    `gh issue view <N> --json ...` read that `status` performs.
    The shim logs the full argv (one space-joined line per call) to
    <shim_dir>/gh-calls.log so the test can assert the native PATCH + comment.
    """
    for num, payload in view_responses.items():
        with open(os.path.join(shim_dir, f"view-{num}.json"), "w") as f:
            f.write(payload)
    log_path = os.path.join(shim_dir, "gh-calls.log")
    shim_path = os.path.join(shim_dir, "gh")
    with open(shim_path, "w") as f:
        f.write("#!/bin/sh\n")
        f.write(f'echo "$@" >> "{log_path}"\n')
        f.write('sub="$1"; verb="$2"\n')
        # gh issue view <N> --json ... -> serve fixture
        f.write('if [ "$sub" = "issue" ] && [ "$verb" = "view" ]; then\n')
        f.write('  num="$3"\n')
        f.write(f'  if [ -f "{shim_dir}/view-${{num}}.json" ]; then\n')
        f.write(f'    cat "{shim_dir}/view-${{num}}.json"\n')
        f.write('  else\n')
        f.write('    printf "{}"\n')
        f.write('  fi\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        # gh api ... (the native PATCH) -> emit a benign closed payload
        f.write('if [ "$sub" = "api" ]; then\n')
        f.write('  printf "{\\"state\\":\\"closed\\",\\"state_reason\\":\\"duplicate\\"}"\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        # gh issue comment ... -> succeed quietly
        f.write('if [ "$sub" = "issue" ] && [ "$verb" = "comment" ]; then\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('exit 0\n')
    os.chmod(shim_path, stat.S_IRWXU)
    return log_path


def run_script(args, shim_dir):
    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, env=env,
    )


# ---------------------------------------------------------------------------
# --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"], capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail("help: expected 'usage' in output")
else:
    ok("help: 'usage' in output")


# ---------------------------------------------------------------------------
# 1. resolve <dup> <canonical> -> native state_reason=duplicate PATCH + comment
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as shim_dir:
    log_path = write_shim(shim_dir, {})
    proc = run_script(["resolve", "103", "90"], shim_dir)
    if proc.returncode != 0:
        fail(f"resolve: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        log = ""
        if os.path.isfile(log_path):
            with open(log_path) as f:
                log = f.read()
        # Native close-as-duplicate PATCH must be issued for the duplicate (103).
        has_patch = (
            "api" in log
            and "PATCH" in log
            and "state=closed" in log
            and "state_reason=duplicate" in log
            and "/issues/103" in log
        )
        if not has_patch:
            fail(f"resolve: expected native PATCH closing #103 with "
                 f"state_reason=duplicate; gh log:\n{log}")
        else:
            ok("resolve: native state_reason=duplicate PATCH issued for #103")
        # The canonical issue (90) must be cross-referenced.
        if "90" not in log:
            fail(f"resolve: expected a cross-reference to canonical #90; "
                 f"gh log:\n{log}")
        else:
            ok("resolve: canonical #90 cross-referenced")
        # 5. resolve must NEVER stamp the reinvented `duplicate` label.
        if "edit" in log and "duplicate" in log and "--add-label" in log:
            fail(f"resolve: must NOT stamp the reinvented `duplicate` label; "
                 f"gh log:\n{log}")
        else:
            ok("resolve: no reinvented `duplicate` label stamped")


# ---------------------------------------------------------------------------
# 2. status <n> -> native stateReason=duplicate is authoritative
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as shim_dir:
    view = json.dumps({
        "number": 200, "state": "CLOSED",
        "stateReason": "duplicate", "labels": [],
    })
    write_shim(shim_dir, {"200": view})
    proc = run_script(["status", "200"], shim_dir)
    if proc.returncode != 0:
        fail(f"status-native: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            res = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            fail(f"status-native: stdout not JSON ({e}); got {proc.stdout!r}")
            res = {}
        if res.get("is_duplicate") is not True:
            fail(f"status-native: native stateReason=duplicate must report "
                 f"is_duplicate=true; got {res!r}")
        elif res.get("source") != "native":
            fail(f"status-native: source must be 'native'; got {res!r}")
        else:
            ok("status-native: native stateReason=duplicate is authoritative")


# ---------------------------------------------------------------------------
# 3. status <n> -> legacy `duplicate` label honored on read (coexistence)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as shim_dir:
    view = json.dumps({
        "number": 201, "state": "CLOSED",
        "stateReason": "not planned",
        "labels": [{"name": "duplicate"}],
    })
    write_shim(shim_dir, {"201": view})
    proc = run_script(["status", "201"], shim_dir)
    if proc.returncode != 0:
        fail(f"status-legacy: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            res = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            fail(f"status-legacy: stdout not JSON ({e}); got {proc.stdout!r}")
            res = {}
        if res.get("is_duplicate") is not True:
            fail(f"status-legacy: legacy `duplicate` label must read as a "
                 f"recognized duplicate; got {res!r}")
        elif res.get("source") != "legacy-label":
            fail(f"status-legacy: source must be 'legacy-label' (deprecating "
                 f"coexistence mirror); got {res!r}")
        else:
            ok("status-legacy: legacy `duplicate` label honored on read")


# ---------------------------------------------------------------------------
# 4. status <n> -> ordinary open issue is NOT a duplicate
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as shim_dir:
    view = json.dumps({
        "number": 202, "state": "OPEN",
        "stateReason": None, "labels": [{"name": "enhancement"}],
    })
    write_shim(shim_dir, {"202": view})
    proc = run_script(["status", "202"], shim_dir)
    if proc.returncode != 0:
        fail(f"status-none: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            res = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            fail(f"status-none: stdout not JSON ({e}); got {proc.stdout!r}")
            res = {}
        if res.get("is_duplicate") is not False:
            fail(f"status-none: an ordinary issue must report is_duplicate="
                 f"false; got {res!r}")
        else:
            ok("status-none: ordinary issue not a duplicate")


sys.exit(FAIL)
