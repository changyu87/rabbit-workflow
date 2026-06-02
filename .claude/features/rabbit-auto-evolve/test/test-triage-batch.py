#!/usr/bin/env python3
"""test-triage-batch.py — e2e tests for scripts/triage-batch.py (Inv 18).

Covers the spec-mandated scenarios for the triage batch bridge:
  - --help smoke test.
  - Happy path: 3 raw fetch-queue issues in stdin → 3 triage objects in
    input order.
  - Per-issue failure: triage-issue.py shim that exits non-zero for issue
    #2 → that issue's slot is filled with decision=defer,
    reason_code=triage-failed; overall exit 0.
  - Malformed stdin JSON → non-zero exit; stderr names the parse error.

The script invokes triage-issue.py as a subprocess. The test seam is the
RABBIT_AUTO_EVOLVE_SCRIPT_DIR env var (per Inv 18) which overrides the
default sibling path resolution for triage-issue.py.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "triage-batch.py"))


FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write_shim(dir_path, body):
    """Write a triage-issue.py shim into dir_path with the given body."""
    path = os.path.join(dir_path, "triage-issue.py")
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def run_batch(items, script_dir):
    """Invoke triage-batch.py with `items` piped as JSON on stdin."""
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(items),
        capture_output=True, text=True,
        env=env,
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
help_text = (proc.stdout + proc.stderr).lower()
if "usage" not in help_text:
    fail(f"help: expected 'usage' in output; got {proc.stdout!r} {proc.stderr!r}")
else:
    ok("help: 'usage' in output")


# ---------------------------------------------------------------------------
# Scenario 1 — Happy path: shim emits a triage object per requested issue.
#   The shim reads its first CLI arg (issue number) and emits a canned
#   triage object pulled from a fixture map.
# ---------------------------------------------------------------------------
HAPPY_SHIM = """#!/usr/bin/env python3
import json
import sys

FIXTURES = {
    "101": {"issue": 101, "decision": "work", "reason_code": "actionable",
            "rationale": "ok", "feature": "alpha", "contract_touch": False,
            "blocked_by": []},
    "102": {"issue": 102, "decision": "close-not-planned",
            "reason_code": "duplicate", "rationale": "dup",
            "feature": "beta", "contract_touch": False, "blocked_by": []},
    "103": {"issue": 103, "decision": "work", "reason_code": "actionable",
            "rationale": "ok", "feature": "gamma", "contract_touch": True,
            "blocked_by": []},
}
arg = sys.argv[1]
json.dump(FIXTURES[arg], sys.stdout)
sys.stdout.write("\\n")
"""

with tempfile.TemporaryDirectory() as tmp:
    _write_shim(tmp, HAPPY_SHIM)
    raw_issues = [
        {"number": 101, "title": "a", "labels": [], "body": "",
         "createdAt": "2026-06-01T00:00:00Z"},
        {"number": 102, "title": "b", "labels": [], "body": "",
         "createdAt": "2026-06-01T00:00:01Z"},
        {"number": 103, "title": "c", "labels": [], "body": "",
         "createdAt": "2026-06-01T00:00:02Z"},
    ]
    proc = run_batch(raw_issues, tmp)
    if proc.returncode != 0:
        fail(f"happy: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            out = json.loads(proc.stdout)
            if not isinstance(out, list) or len(out) != 3:
                fail(f"happy: expected 3-item array, got {out!r}")
            else:
                issues = [o.get("issue") for o in out]
                if issues != [101, 102, 103]:
                    fail(f"happy: input-order broken; got {issues!r}")
                elif out[0].get("decision") != "work":
                    fail(f"happy: out[0] decision != work; {out[0]!r}")
                elif out[1].get("decision") != "close-not-planned":
                    fail(f"happy: out[1] decision != close-not-planned; {out[1]!r}")
                else:
                    ok("happy: 3 triage objects emitted in input order")
        except json.JSONDecodeError as e:
            fail(f"happy: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 2 — Per-issue failure: shim exits non-zero for issue #202; the
#   other two succeed; batch overall exits 0 and issue #202 gets a
#   defer/triage-failed entry.
# ---------------------------------------------------------------------------
FAIL_SHIM = """#!/usr/bin/env python3
import json
import sys

arg = sys.argv[1]
if arg == "202":
    sys.stderr.write("simulated triage failure for 202\\n")
    sys.exit(1)
json.dump({
    "issue": int(arg),
    "decision": "work",
    "reason_code": "actionable",
    "rationale": "ok",
    "feature": "alpha",
    "contract_touch": False,
    "blocked_by": [],
}, sys.stdout)
sys.stdout.write("\\n")
"""

with tempfile.TemporaryDirectory() as tmp:
    _write_shim(tmp, FAIL_SHIM)
    raw_issues = [
        {"number": 201, "title": "a", "labels": [], "body": "",
         "createdAt": "2026-06-01T00:00:00Z"},
        {"number": 202, "title": "b", "labels": [], "body": "",
         "createdAt": "2026-06-01T00:00:01Z"},
        {"number": 203, "title": "c", "labels": [], "body": "",
         "createdAt": "2026-06-01T00:00:02Z"},
    ]
    proc = run_batch(raw_issues, tmp)
    if proc.returncode != 0:
        fail(f"per-issue-failure: overall exit {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        try:
            out = json.loads(proc.stdout)
            if len(out) != 3:
                fail(f"per-issue-failure: expected 3 entries, got {len(out)}")
            else:
                slot = next((o for o in out if o.get("issue") == 202), None)
                if slot is None:
                    fail(f"per-issue-failure: issue 202 slot missing: {out!r}")
                elif slot.get("decision") != "defer":
                    fail(f"per-issue-failure: 202 decision != defer; {slot!r}")
                elif slot.get("reason_code") != "triage-failed":
                    fail(f"per-issue-failure: 202 reason_code != triage-failed; {slot!r}")
                else:
                    others = [o for o in out if o.get("issue") in (201, 203)]
                    if not all(o.get("decision") == "work" for o in others):
                        fail(f"per-issue-failure: other slots not 'work'; {others!r}")
                    else:
                        ok("per-issue-failure: 202 deferred as triage-failed; others ok")
        except json.JSONDecodeError as e:
            fail(f"per-issue-failure: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 3 — Malformed stdin JSON → non-zero exit; stderr names parse error.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    _write_shim(tmp, HAPPY_SHIM)
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = tmp
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input="not valid json{{{",
        capture_output=True, text=True,
        env=env,
    )
    if proc.returncode == 0:
        fail("malformed-stdin: should exit non-zero")
    else:
        stderr_lower = proc.stderr.lower()
        if "json" not in stderr_lower and "parse" not in stderr_lower:
            fail(f"malformed-stdin: stderr should mention parse error; "
                 f"got {proc.stderr!r}")
        else:
            ok("malformed-stdin: exit non-zero, stderr names parse error")


# ---------------------------------------------------------------------------
# Scenario 4 — Empty input array: clean no-op, emits "[]" on stdout, exit 0.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    _write_shim(tmp, HAPPY_SHIM)
    proc = run_batch([], tmp)
    if proc.returncode != 0:
        fail(f"empty: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            out = json.loads(proc.stdout)
            if out != []:
                fail(f"empty: expected [], got {out!r}")
            else:
                ok("empty: empty input → empty output array")
        except json.JSONDecodeError as e:
            fail(f"empty: bad JSON ({e}); stdout={proc.stdout!r}")


sys.exit(FAIL)
