#!/usr/bin/env python3
"""test-release-bump.py — e2e tests for scripts/release-bump.py (Inv 7).

Covers the spec'd surface of `scripts/release-bump.py`:
  - --help smoke
  - one test per bump-table row (5 cases): body-directive (major),
    feature-count-threshold (major), contract-schema-touch (major),
    priority-high-critical (minor), priority-low-medium (patch)
  - safety-check fail → status: skipped, reason: safety-check-failed,
    AND `git tag` is NEVER invoked (verifiable via shim call log)
  - --features-threshold 5 override: 4 distinct features touched bumps
    minor, not major
  - closing-issue priority fallback (issue #529): when the PR carries NO
    priority:<level> label, the closing issue named in the PR body
    (Fixes|Closes|Resolves #N, case-insensitive) is consulted and its
    priority label drives the bump. An explicit priority label ON the PR
    still wins (precedence). No closing issue / no issue priority → patch.

Fixtures use a tempdir on PATH carrying:
  - a `gh` shim that responds to `gh pr view --json` with a per-test
    JSON payload, to `gh issue view <N> --json labels` with a per-issue
    labels payload, and to `gh release create` by recording the call
  - a `git` shim that records `git describe`, `git tag`, `git push` calls
    (and serves `git describe --tags --abbrev=0` with a configurable
    prior tag); other git subcommands delegate to the real git binary
  - a `safety-check.py` shim alongside the script that exits 0 by default

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
    os.path.join(HERE, "..", "scripts", "release-bump.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write_gh_shim(shim_dir, call_log, pr_view_payload, issue_labels=None):
    """gh shim:
       - `gh pr view <#> --json ...` echoes the JSON payload provided
       - `gh issue view <N> --json labels` echoes `{"labels": [...]}` for
         issue N when N is in `issue_labels` (maps issue number -> list of
         label-name strings); unknown issue numbers exit non-zero like a
         missing issue (issue #529 closing-issue priority fallback)
       - `gh release create ...` records the call and exits 0
       - All calls recorded to call_log (prefixed with 'gh ')
    """
    shim = os.path.join(shim_dir, "gh")
    payload_str = json.dumps(pr_view_payload)
    issue_labels = issue_labels or {}
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        f.write(f'CALL_LOG="{call_log}"\n')
        f.write('printf "gh %s\\n" "$*" >> "$CALL_LOG"\n')
        f.write('SUB="$1"; shift\n')
        f.write('ACTION="$1"; shift\n')
        f.write('if [ "$SUB" = "pr" ] && [ "$ACTION" = "view" ]; then\n')
        # gh pr view --json fields ... — emit the payload.
        f.write(f"  cat <<'PAYLOAD_EOF'\n{payload_str}\nPAYLOAD_EOF\n")
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('if [ "$SUB" = "issue" ] && [ "$ACTION" = "view" ]; then\n')
        # gh issue view <N> --json labels — $1 is the issue number.
        f.write('  ISSUE="$1"\n')
        f.write('  case "$ISSUE" in\n')
        for num, labels in issue_labels.items():
            ip = json.dumps({"labels": [{"name": n} for n in labels]})
            f.write(f"    {num})\n")
            f.write(f"      cat <<'ISSUE_EOF'\n{ip}\nISSUE_EOF\n")
            f.write('      exit 0 ;;\n')
        f.write('    *)\n')
        f.write('      echo "no issue found" >&2\n')
        f.write('      exit 1 ;;\n')
        f.write('  esac\n')
        f.write('fi\n')
        f.write('if [ "$SUB" = "release" ] && [ "$ACTION" = "create" ]; then\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('exit 0\n')
    os.chmod(shim, stat.S_IRWXU)


def _write_git_shim(shim_dir, call_log, prior_tag="v0.5.2",
                    tag_exit=0, push_exit=0, describe_exit=0):
    """git shim:
       - `git describe --tags --abbrev=0` echoes `prior_tag` and exits
         `describe_exit` (set non-zero to simulate a tag-free repo, where
         real git writes "fatal: No names found ..." to stderr and exits
         128 — issue #400 first-release case)
       - `git tag -a <tag> -m <msg>` records and exits tag_exit
       - `git push origin <tag>` records and exits push_exit
       - Other git subcommands delegate to the real git binary
    """
    real_git = subprocess.check_output(["which", "git"]).decode().strip()
    shim = os.path.join(shim_dir, "git")
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n")
        f.write(f'CALL_LOG="{call_log}"\n')
        f.write(f'REAL_GIT="{real_git}"\n')
        f.write(f'PRIOR_TAG="{prior_tag}"\n')
        f.write(f'TAG_EXIT={tag_exit}\n')
        f.write(f'PUSH_EXIT={push_exit}\n')
        f.write(f'DESCRIBE_EXIT={describe_exit}\n')
        f.write('printf "git %s\\n" "$*" >> "$CALL_LOG"\n')
        # git describe --tags --abbrev=0 (any arg order, but match the literal)
        f.write('if [ "$1" = "describe" ]; then\n')
        f.write('  if [ "$DESCRIBE_EXIT" -ne 0 ]; then\n')
        f.write('    echo "fatal: No names found, cannot describe anything." >&2\n')
        f.write('    exit "$DESCRIBE_EXIT"\n')
        f.write('  fi\n')
        f.write('  printf "%s\\n" "$PRIOR_TAG"\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        # git tag -a <name> -m <msg>
        f.write('if [ "$1" = "tag" ]; then\n')
        f.write('  exit $TAG_EXIT\n')
        f.write('fi\n')
        # git push origin <tag>
        f.write('if [ "$1" = "push" ]; then\n')
        f.write('  exit $PUSH_EXIT\n')
        f.write('fi\n')
        # Delegate.
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


def _make_env(tmpdir, pr_view_payload,
              prior_tag="v0.5.2",
              tag_exit=0, push_exit=0,
              safety_exit=0, describe_exit=0,
              issue_labels=None):
    bin_dir = os.path.join(tmpdir, "bin")
    os.makedirs(bin_dir)
    script_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(script_dir)
    call_log = os.path.join(tmpdir, "calls.log")
    open(call_log, "w").close()

    _write_gh_shim(bin_dir, call_log, pr_view_payload,
                   issue_labels=issue_labels)
    _write_git_shim(bin_dir, call_log, prior_tag=prior_tag,
                    tag_exit=tag_exit, push_exit=push_exit,
                    describe_exit=describe_exit)
    _write_safety_shim(script_dir, exit_code=safety_exit)

    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    # Inv 61: clear any inherited integration-target so the default (main)
    # resolves unless a test sets it explicitly.
    env.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
    return tmpdir, env, call_log


def _calls(call_log):
    with open(call_log) as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _run(cwd, env, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def _make_payload(*, labels=None, body="", files=None, number=42,
                  title="Test PR"):
    return {
        "number": number,
        "title": title,
        "labels": [{"name": n} for n in (labels or [])],
        "body": body,
        "files": [{"path": p} for p in (files or [])],
    }


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
# Inv 61: `gh release create` targets the resolved integration target, which is
# now constantly `main` (the coexistence window has closed). The (removed)
# RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET env var is IGNORED — setting it does not
# change the release target.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(labels=["priority:low"], body="x",
                            files=[".claude/features/foo/scripts/a.py"])
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"target-default: exit {proc.returncode}; stderr={proc.stderr!r}")
    rel_calls = [c for c in _calls(call_log) if c.startswith("gh release create")]
    if not rel_calls:
        fail(f"target-default: no gh release create call; calls logged")
    elif not any("--target main" in c for c in rel_calls):
        fail(f"target-default: gh release create missing '--target main'; "
             f"{rel_calls!r}")
    else:
        ok("target-default: gh release create --target main (sole target)")

with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(labels=["priority:low"], body="x",
                            files=[".claude/features/foo/scripts/a.py"])
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = "dev"
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"target-env-ignored: exit {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    rel_calls = [c for c in _calls(call_log) if c.startswith("gh release create")]
    if not rel_calls:
        fail("target-env-ignored: no gh release create call")
    elif not any("--target main" in c for c in rel_calls):
        fail(f"target-env-ignored: gh release create missing '--target main' "
             f"(the removed env var must be ignored); {rel_calls!r}")
    else:
        ok("target-env-ignored: removed env var ignored → --target main")


# ---------------------------------------------------------------------------
# Bump-table row 1: body contains 'bump:major' → major / body-directive.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:low"],  # priority alone would be patch
        body="Some text.\n\nbump:major\n\nMore text.",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"row1: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"row1: stdout not JSON: {e}; stdout={proc.stdout!r}")
        result = None
    if result is not None:
        if result.get("bump") != "major":
            fail(f"row1: bump {result.get('bump')!r} != 'major'")
        elif result.get("trigger") != "body-directive":
            fail(f"row1: trigger {result.get('trigger')!r} "
                 f"!= 'body-directive'")
        elif result.get("next_tag") != "v1.0.0":
            fail(f"row1: next_tag {result.get('next_tag')!r} != 'v1.0.0'")
        else:
            ok("row1: body 'bump:major' → major / body-directive / v1.0.0")


# ---------------------------------------------------------------------------
# Bump-table row 2: ≥ 3 distinct top-level features → major /
# feature-count-threshold.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:low"],
        body="No directive here.",
        files=[
            ".claude/features/foo/scripts/a.py",
            ".claude/features/bar/scripts/b.py",
            ".claude/features/baz/scripts/c.py",
        ],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"row2: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"row2: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "major":
            fail(f"row2: bump {result.get('bump')!r} != 'major'")
        elif result.get("trigger") != "feature-count-threshold":
            fail(f"row2: trigger {result.get('trigger')!r} "
                 f"!= 'feature-count-threshold'")
        elif result.get("next_tag") != "v1.0.0":
            fail(f"row2: next_tag {result.get('next_tag')!r} != 'v1.0.0'")
        else:
            ok("row2: 3 distinct features → major / feature-count-threshold")


# ---------------------------------------------------------------------------
# Bump-table row 3: any contract/schemas/ touch → major /
# contract-schema-touch.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:low"],
        body="No directive here.",
        files=[
            ".claude/features/contract/schemas/some.schema.json",
            ".claude/features/foo/scripts/a.py",
        ],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"row3: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"row3: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "major":
            fail(f"row3: bump {result.get('bump')!r} != 'major'")
        elif result.get("trigger") != "contract-schema-touch":
            fail(f"row3: trigger {result.get('trigger')!r} "
                 f"!= 'contract-schema-touch'")
        else:
            ok("row3: contract/schemas/ touch → major / contract-schema-touch")


# ---------------------------------------------------------------------------
# Bump-table row 4: priority:high or priority:critical → minor /
# priority-high-critical.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:high"],
        body="No directive.",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"row4: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"row4: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "minor":
            fail(f"row4: bump {result.get('bump')!r} != 'minor'")
        elif result.get("trigger") != "priority-high-critical":
            fail(f"row4: trigger {result.get('trigger')!r} "
                 f"!= 'priority-high-critical'")
        elif result.get("next_tag") != "v0.6.0":
            fail(f"row4: next_tag {result.get('next_tag')!r} != 'v0.6.0'")
        else:
            ok("row4: priority:high → minor / priority-high-critical / v0.6.0")


# ---------------------------------------------------------------------------
# Bump-table row 5: priority:low or priority:medium → patch /
# priority-low-medium.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:medium"],
        body="No directive.",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"row5: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"row5: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "patch":
            fail(f"row5: bump {result.get('bump')!r} != 'patch'")
        elif result.get("trigger") != "priority-low-medium":
            fail(f"row5: trigger {result.get('trigger')!r} "
                 f"!= 'priority-low-medium'")
        elif result.get("next_tag") != "v0.5.3":
            fail(f"row5: next_tag {result.get('next_tag')!r} != 'v0.5.3'")
        else:
            ok("row5: priority:medium → patch / priority-low-medium / v0.5.3")


# ---------------------------------------------------------------------------
# Safety-check fail: shim exits non-zero. Expected:
#   - status: skipped, reason: safety-check-failed
#   - `git tag` is NEVER invoked (verifiable via call log)
#   - exit 0 (per "Exit 0 always except argparse/unexpected")
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:medium"],
        body="",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(
        td, payload, prior_tag="v0.5.2", safety_exit=2,
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"safety-fail: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"safety-fail: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("status") != "skipped":
            fail(f"safety-fail: status {result.get('status')!r} "
                 f"!= 'skipped'")
        elif result.get("reason") != "safety-check-failed":
            fail(f"safety-fail: reason {result.get('reason')!r} "
                 f"!= 'safety-check-failed'")
        else:
            ok("safety-fail: status=skipped, reason=safety-check-failed")
    calls = _calls(call_log)
    # `git tag` is the destructive call we must NOT have made.
    if any(c.startswith("git tag") for c in calls):
        fail(f"safety-fail: git tag was invoked despite safety-check fail; "
             f"calls={calls!r}")
    else:
        ok("safety-fail: git tag was NOT invoked")


# ---------------------------------------------------------------------------
# --features-threshold override: 4 distinct features touched, threshold=5,
# no other major trigger, with priority:high → minor (not major).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:high"],
        body="No directive.",
        files=[
            ".claude/features/foo/scripts/a.py",
            ".claude/features/bar/scripts/b.py",
            ".claude/features/baz/scripts/c.py",
            ".claude/features/qux/scripts/d.py",
        ],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42", "--features-threshold", "5")
    if proc.returncode != 0:
        fail(f"threshold: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"threshold: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "minor":
            fail(f"threshold: bump {result.get('bump')!r} != 'minor' "
                 f"(4 features under threshold 5 should NOT trigger major)")
        elif result.get("trigger") != "priority-high-critical":
            fail(f"threshold: trigger {result.get('trigger')!r} "
                 f"!= 'priority-high-critical'")
        else:
            ok("threshold: --features-threshold 5 keeps 4-feature change minor")


# ---------------------------------------------------------------------------
# Happy-path full release: confirm status=released and git tag was invoked.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:medium"],
        body="",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"happy: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"happy: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("status") != "released":
            fail(f"happy: status {result.get('status')!r} != 'released'")
        elif result.get("prior_tag") != "v0.5.2":
            fail(f"happy: prior_tag {result.get('prior_tag')!r} != 'v0.5.2'")
        elif result.get("next_tag") != "v0.5.3":
            fail(f"happy: next_tag {result.get('next_tag')!r} != 'v0.5.3'")
        else:
            ok("happy: released; prior=v0.5.2 next=v0.5.3")
    calls = _calls(call_log)
    if not any(c.startswith("git tag") for c in calls):
        fail(f"happy: git tag was NOT invoked; calls={calls!r}")
    else:
        ok("happy: git tag was invoked")


# ---------------------------------------------------------------------------
# First release (issue #400): zero prior tags. `git describe` exits non-zero.
# The script must NOT crash; first tag is v1.0.0 regardless of bump kind, and
# git tag IS invoked. Covers priority:high (would-be minor),
# priority:critical (would-be major), and priority:low (would-be patch).
# ---------------------------------------------------------------------------
for label, would_be in (
    ("priority:high", "minor"),
    ("priority:critical", "major"),
    ("priority:low", "patch"),
):
    with tempfile.TemporaryDirectory() as td:
        payload = _make_payload(
            labels=[label],
            body="",
            files=[".claude/features/foo/scripts/a.py"],
        )
        cwd, env, call_log = _make_env(td, payload, describe_exit=128)
        proc = _run(cwd, env, "42")
        if proc.returncode != 0:
            fail(f"first-release[{label}]: exit {proc.returncode}; "
                 f"stderr={proc.stderr!r}")
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            fail(f"first-release[{label}]: stdout not JSON: {e}; "
                 f"stdout={proc.stdout!r}")
            result = None
        if result is not None:
            if result.get("status") != "released":
                fail(f"first-release[{label}]: status "
                     f"{result.get('status')!r} != 'released'")
            elif result.get("prior_tag") is not None:
                fail(f"first-release[{label}]: prior_tag "
                     f"{result.get('prior_tag')!r} != None")
            elif result.get("next_tag") != "v1.0.0":
                fail(f"first-release[{label}]: next_tag "
                     f"{result.get('next_tag')!r} != 'v1.0.0' "
                     f"(would-be {would_be})")
            else:
                ok(f"first-release[{label}]: zero tags → v1.0.0 / released")
        calls = _calls(call_log)
        if not any(c.startswith("git tag") for c in calls):
            fail(f"first-release[{label}]: git tag NOT invoked; "
                 f"calls={calls!r}")
        else:
            ok(f"first-release[{label}]: git tag invoked for first release")


# ---------------------------------------------------------------------------
# Closing-issue priority fallback (issue #529): PR carries NO priority label
# but its body says "Closes #777" where issue 777 is priority:high →
# minor / priority-high-critical (the NEW behaviour). The bump must come
# from the closing issue, not the patch default.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=[],  # PR has NO priority label
        body="Implements the thing.\n\nCloses #777\n",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(
        td, payload, prior_tag="v0.5.2",
        issue_labels={777: ["priority:high"]},
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"close-issue-high: exit {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"close-issue-high: stdout not JSON: {e}; stdout={proc.stdout!r}")
        result = None
    if result is not None:
        if result.get("bump") != "minor":
            fail(f"close-issue-high: bump {result.get('bump')!r} != 'minor' "
                 f"(should fall back to closing issue #777 priority:high)")
        elif result.get("trigger") != "priority-high-critical":
            fail(f"close-issue-high: trigger {result.get('trigger')!r} "
                 f"!= 'priority-high-critical'")
        elif result.get("next_tag") != "v0.6.0":
            fail(f"close-issue-high: next_tag {result.get('next_tag')!r} "
                 f"!= 'v0.6.0'")
        else:
            ok("close-issue-high: PR no-label + Closes #777(high) → minor")


# ---------------------------------------------------------------------------
# Closing-issue ref is case-insensitive and supports Fixes/Resolves:
# body "resolves #88" where issue 88 is priority:critical → minor.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=[],
        body="Fix.\n\nresolves #88\n",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(
        td, payload, prior_tag="v0.5.2",
        issue_labels={88: ["priority:critical"]},
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"close-issue-ci: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"close-issue-ci: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "minor":
            fail(f"close-issue-ci: bump {result.get('bump')!r} != 'minor' "
                 f"(case-insensitive 'resolves #88' should resolve)")
        elif result.get("trigger") != "priority-high-critical":
            fail(f"close-issue-ci: trigger {result.get('trigger')!r} "
                 f"!= 'priority-high-critical'")
        else:
            ok("close-issue-ci: 'resolves #88'(critical) → minor (case-insens)")


# ---------------------------------------------------------------------------
# PR priority label PRECEDES the closing issue's: PR is priority:low while
# the closing issue #777 is priority:high. The PR label wins → patch.
# (Unchanged precedence: an explicit PR label is authoritative.)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:low"],  # explicit PR label present
        body="Closes #777\n",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(
        td, payload, prior_tag="v0.5.2",
        issue_labels={777: ["priority:high"]},
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"pr-wins: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"pr-wins: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "patch":
            fail(f"pr-wins: bump {result.get('bump')!r} != 'patch' "
                 f"(explicit PR priority:low must win over issue priority:high)")
        elif result.get("trigger") != "priority-low-medium":
            fail(f"pr-wins: trigger {result.get('trigger')!r} "
                 f"!= 'priority-low-medium'")
        else:
            ok("pr-wins: PR priority:low beats closing-issue priority:high")
    # Precedence also means the issue lookup is short-circuited: no
    # `gh issue view` call should have been made.
    calls = _calls(call_log)
    if any(c.startswith("gh issue view") for c in calls):
        fail(f"pr-wins: gh issue view was called despite explicit PR label; "
             f"calls={calls!r}")
    else:
        ok("pr-wins: closing-issue lookup short-circuited (no gh issue view)")


# ---------------------------------------------------------------------------
# Neither PR nor closing issue has a priority label → patch (default,
# unchanged). PR has no label; body "Closes #5"; issue 5 has no priority.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=[],
        body="Closes #5\n",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(
        td, payload, prior_tag="v0.5.2",
        issue_labels={5: ["type:bug"]},  # no priority:* label
    )
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"both-unlabeled: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"both-unlabeled: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "patch":
            fail(f"both-unlabeled: bump {result.get('bump')!r} != 'patch'")
        elif result.get("trigger") != "priority-low-medium":
            fail(f"both-unlabeled: trigger {result.get('trigger')!r} "
                 f"!= 'priority-low-medium'")
        else:
            ok("both-unlabeled: PR + closing issue both unlabeled → patch")


# ---------------------------------------------------------------------------
# No closing-issue reference at all + no PR priority label → patch (default).
# The script must NOT crash when the body names no issue.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=[],
        body="A change with no issue reference.",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"no-ref: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"no-ref: stdout not JSON: {e}")
        result = None
    if result is not None:
        if result.get("bump") != "patch":
            fail(f"no-ref: bump {result.get('bump')!r} != 'patch'")
        elif result.get("trigger") != "priority-low-medium":
            fail(f"no-ref: trigger {result.get('trigger')!r} "
                 f"!= 'priority-low-medium'")
        else:
            ok("no-ref: no closing issue, no PR label → patch")


# ===========================================================================
# Issue #564 — when release-bump.py cuts a release, it writes the new tag
# into `last_tagged_version` in the on-disk state. No phase script previously
# persisted this field, so it lagged perpetually; phase-10's deterministic
# re-read (update-state.py) then captures it. The write mirrors the
# read-modify-write pattern merge-prs.py uses for pending_post_merge.
# ===========================================================================

def _state_path(state_dir):
    return os.path.join(state_dir, "auto-evolve-state.json")


def _seed_state(state_dir, last_tagged_version=None):
    state = {
        "schema_version": "1.4.0",
        "updated_at": "2026-06-03T00:00:00Z",
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": last_tagged_version,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
    }
    with open(_state_path(state_dir), "w") as f:
        json.dump(state, f)


# --- (A) released → last_tagged_version equals next_tag --------------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:medium"],
        body="",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(td, payload, prior_tag="v0.5.2")
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir)
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    proc = _run(cwd, env, "42")
    if proc.returncode != 0:
        fail(f"last-tagged: exit {proc.returncode}; stderr={proc.stderr!r}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"last-tagged: stdout not JSON: {e}")
        result = None
    if result is not None and result.get("status") != "released":
        fail(f"last-tagged: status {result.get('status')!r} != 'released'")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if state.get("last_tagged_version") != "v0.5.3":
        fail(f"last-tagged: last_tagged_version "
             f"{state.get('last_tagged_version')!r} != 'v0.5.3' (issue #564)")
    else:
        ok("last-tagged: state.last_tagged_version == cut tag")


# --- (B) safety-check fail (skipped) → last_tagged_version untouched -------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:medium"],
        body="",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(
        td, payload, prior_tag="v0.5.2", safety_exit=2,
    )
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, last_tagged_version="v0.5.2")
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    proc = _run(cwd, env, "42")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if state.get("last_tagged_version") != "v0.5.2":
        fail(f"last-tagged-skip: a skipped release overwrote "
             f"last_tagged_version to {state.get('last_tagged_version')!r} "
             f"(should stay 'v0.5.2')")
    else:
        ok("last-tagged-skip: skipped release → last_tagged_version preserved")


# --- (C) git tag fail (failed) → last_tagged_version untouched -------------
with tempfile.TemporaryDirectory() as td:
    payload = _make_payload(
        labels=["priority:medium"],
        body="",
        files=[".claude/features/foo/scripts/a.py"],
    )
    cwd, env, call_log = _make_env(
        td, payload, prior_tag="v0.5.2", tag_exit=1,
    )
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    _seed_state(state_dir, last_tagged_version="v0.5.2")
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    proc = _run(cwd, env, "42")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result = None
    if result is not None and result.get("status") != "failed":
        fail(f"last-tagged-fail: status {result.get('status')!r} != 'failed'")
    with open(_state_path(state_dir)) as f:
        state = json.load(f)
    if state.get("last_tagged_version") != "v0.5.2":
        fail(f"last-tagged-fail: a failed release overwrote "
             f"last_tagged_version to {state.get('last_tagged_version')!r} "
             f"(should stay 'v0.5.2')")
    else:
        ok("last-tagged-fail: failed release → last_tagged_version preserved")


sys.exit(FAIL)
