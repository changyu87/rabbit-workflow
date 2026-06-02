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

Fixtures use a tempdir on PATH carrying:
  - a `gh` shim that responds to `gh pr view --json` with a per-test
    JSON payload, and to `gh release create` by recording the call
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


def _write_gh_shim(shim_dir, call_log, pr_view_payload):
    """gh shim:
       - `gh pr view <#> --json ...` echoes the JSON payload provided
       - `gh release create ...` records the call and exits 0
       - All calls recorded to call_log (prefixed with 'gh ')
    """
    shim = os.path.join(shim_dir, "gh")
    payload_str = json.dumps(pr_view_payload)
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
        f.write('if [ "$SUB" = "release" ] && [ "$ACTION" = "create" ]; then\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('exit 0\n')
    os.chmod(shim, stat.S_IRWXU)


def _write_git_shim(shim_dir, call_log, prior_tag="v0.5.2",
                    tag_exit=0, push_exit=0):
    """git shim:
       - `git describe --tags --abbrev=0` echoes `prior_tag`
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
        f.write('printf "git %s\\n" "$*" >> "$CALL_LOG"\n')
        # git describe --tags --abbrev=0 (any arg order, but match the literal)
        f.write('if [ "$1" = "describe" ]; then\n')
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
              safety_exit=0):
    bin_dir = os.path.join(tmpdir, "bin")
    os.makedirs(bin_dir)
    script_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(script_dir)
    call_log = os.path.join(tmpdir, "calls.log")
    open(call_log, "w").close()

    _write_gh_shim(bin_dir, call_log, pr_view_payload)
    _write_git_shim(bin_dir, call_log, prior_tag=prior_tag,
                    tag_exit=tag_exit, push_exit=push_exit)
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


sys.exit(FAIL)
