#!/usr/bin/env python3
"""test-fetch-queue.py — e2e tests for scripts/fetch-queue.py (Inv 2).

Covers the two spec-mandated scenarios:
  A) --help smoke test — exit 0 and recognizable usage text.
  B) Sort-order test — tempdir + PATH-resident `gh` shim emits a fixture
     mixing all four priorities plus a no-priority issue, with
     non-monotonic createdAt within buckets. Script output JSON must be
     sorted by priority (critical > high > medium > low > no-priority)
     then createdAt ascending within each bucket.

The script is run as a subprocess so the on-PATH `gh` shim is honored.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "fetch-queue.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# ---------------------------------------------------------------------------
# Scenario A — --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    fail(f"A: --help should exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("A: --help exited 0")
help_text = (proc.stdout + proc.stderr).lower()
if "usage" not in help_text:
    fail(f"A: --help output should contain 'usage'; got stdout={proc.stdout!r} stderr={proc.stderr!r}")
else:
    ok("A: --help output contains 'usage'")


# ---------------------------------------------------------------------------
# Scenario B — sort-order test with PATH-resident `gh` shim
# ---------------------------------------------------------------------------
# Fixture: mix all four priorities plus a no-priority issue. Within each
# priority bucket, createdAt is intentionally non-monotonic so a stable
# sort would NOT produce the expected order — only an explicit
# (priority_rank, createdAt) key sort will.
FIXTURE = [
    # critical bucket — out-of-order createdAt
    {"number": 11, "title": "crit-late",   "labels": [{"name": "rabbit-managed"}, {"name": "priority:critical"}], "body": "", "createdAt": "2026-05-30T12:00:00Z"},
    {"number": 12, "title": "crit-early",  "labels": [{"name": "rabbit-managed"}, {"name": "priority:critical"}], "body": "", "createdAt": "2026-05-30T08:00:00Z"},
    # low bucket
    {"number": 21, "title": "low-late",    "labels": [{"name": "rabbit-managed"}, {"name": "priority:low"}],      "body": "", "createdAt": "2026-05-01T20:00:00Z"},
    {"number": 22, "title": "low-early",   "labels": [{"name": "rabbit-managed"}, {"name": "priority:low"}],      "body": "", "createdAt": "2026-05-01T10:00:00Z"},
    # high bucket
    {"number": 31, "title": "high-late",   "labels": [{"name": "rabbit-managed"}, {"name": "priority:high"}],     "body": "", "createdAt": "2026-05-15T18:00:00Z"},
    {"number": 32, "title": "high-early",  "labels": [{"name": "rabbit-managed"}, {"name": "priority:high"}],     "body": "", "createdAt": "2026-05-15T06:00:00Z"},
    # no-priority bucket
    {"number": 41, "title": "nopri-late",  "labels": [{"name": "rabbit-managed"}],                                 "body": "", "createdAt": "2026-04-20T22:00:00Z"},
    {"number": 42, "title": "nopri-early", "labels": [{"name": "rabbit-managed"}],                                 "body": "", "createdAt": "2026-04-20T02:00:00Z"},
    # medium bucket
    {"number": 51, "title": "med-late",    "labels": [{"name": "rabbit-managed"}, {"name": "priority:medium"}],   "body": "", "createdAt": "2026-05-20T16:00:00Z"},
    {"number": 52, "title": "med-early",   "labels": [{"name": "rabbit-managed"}, {"name": "priority:medium"}],   "body": "", "createdAt": "2026-05-20T04:00:00Z"},
]

with tempfile.TemporaryDirectory() as shim_dir:
    shim_path = os.path.join(shim_dir, "gh")
    fixture_json = json.dumps(FIXTURE)
    # Shell shim: ignore all arguments and emit the fixture JSON on stdout.
    with open(shim_path, "w") as f:
        f.write("#!/bin/sh\n")
        f.write("cat <<'__GH_FIXTURE_EOF__'\n")
        f.write(fixture_json + "\n")
        f.write("__GH_FIXTURE_EOF__\n")
    os.chmod(shim_path, stat.S_IRWXU)

    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")

    proc = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0:
        fail(f"B: expected exit 0 with shim, got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("B: invocation against gh-shim exited 0")

    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"B: stdout is not valid JSON ({e}); got {proc.stdout!r}")
        out = None

    if out is not None:
        if not isinstance(out, list):
            fail(f"B: expected JSON array, got {type(out).__name__}")
        elif len(out) != len(FIXTURE):
            fail(f"B: expected {len(FIXTURE)} issues, got {len(out)}")
        else:
            # Build (priority_rank, createdAt) sequence and verify it is
            # monotonically non-decreasing.
            RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

            def keyfor(issue):
                labels = {lbl["name"] for lbl in issue.get("labels", [])}
                rank = 4  # no-priority sentinel
                for name in labels:
                    if name.startswith("priority:"):
                        pri = name.split(":", 1)[1]
                        if pri in RANK:
                            rank = RANK[pri]
                            break
                return (rank, issue["createdAt"])

            seq = [keyfor(i) for i in out]
            sorted_seq = sorted(seq)
            if seq != sorted_seq:
                fail(f"B: output not sorted by (priority, createdAt); got {seq}")
            else:
                ok("B: output sorted by (priority, createdAt)")

            # Verify no-priority issues land last.
            last_two_titles = {out[-1]["title"], out[-2]["title"]}
            if last_two_titles != {"nopri-early", "nopri-late"}:
                fail(f"B: expected no-priority issues last, got tail titles {last_two_titles}")
            else:
                ok("B: no-priority issues sort to end")

            # Verify within-bucket asc createdAt for the critical bucket
            # specifically (highest-priority bucket — most important to
            # surface first).
            crit = [i for i in out if any(lbl["name"] == "priority:critical" for lbl in i.get("labels", []))]
            if [i["title"] for i in crit] != ["crit-early", "crit-late"]:
                fail(f"B: critical-bucket order wrong: {[i['title'] for i in crit]}")
            else:
                ok("B: critical bucket sorted by createdAt asc")


sys.exit(FAIL)
