#!/usr/bin/env python3
"""test-fetch-queue.py — e2e tests for scripts/fetch-queue.py (Inv 2).

Covers the spec-mandated scenarios:
  A) --help smoke test — exit 0 and recognizable usage text.
  B) Sort-order test — tempdir + PATH-resident `gh` shim emits a fixture
     mixing all four priorities plus a no-priority issue, with
     non-monotonic createdAt within buckets. Script output JSON must be
     sorted by priority (critical > high > medium > low > no-priority)
     then createdAt ascending within each bucket.
  C) --detect-leaks de-queue leak detector (Inv 59 / #731) — coexistence:
     STILL tolerates rabbit-managed, surfaces de-queued open issues.
  D) Actionability-based selection (Inv 2 / #758, coexistence step 1 of
     #753): the queue is OPEN issues with BOTH a valid `feature:` label AND
     a valid `priority:` label — NOT keyed on `rabbit-managed`. A synthetic
     OPEN issue carrying feature:+priority: but NO rabbit-managed label is
     SELECTED (label-independence), while an OPEN issue lacking either a
     feature: or a priority: label is NOT selected. rabbit-managed remains
     tolerated (selected issues may still carry it).

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


def run_with_shim(fixture, extra_args=None):
    """Run fetch-queue.py with a PATH-resident `gh` shim emitting `fixture`.
    Returns (returncode, stdout, stderr)."""
    extra_args = extra_args or []
    with tempfile.TemporaryDirectory() as shim_dir:
        shim_path = os.path.join(shim_dir, "gh")
        fixture_json = json.dumps(fixture)
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
            [sys.executable, SCRIPT] + extra_args,
            capture_output=True, text=True, env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# Scenario B — sort-order test with PATH-resident `gh` shim
# ---------------------------------------------------------------------------
# Fixture: mix all four priorities. Every issue carries BOTH a valid
# `feature:` label AND a valid `priority:` label, so all are actionable and
# selected (Inv 2 / #758). Within each priority bucket, createdAt is
# intentionally non-monotonic so a stable sort would NOT produce the expected
# order — only an explicit (priority_rank, createdAt) key sort will. Issues
# also still carry `rabbit-managed` (tolerated during #753 coexistence).
FIXTURE = [
    # critical bucket — out-of-order createdAt
    {"number": 11, "title": "crit-late",   "labels": [{"name": "rabbit-managed"}, {"name": "feature:rabbit-auto-evolve"}, {"name": "priority:critical"}], "body": "", "createdAt": "2026-05-30T12:00:00Z"},
    {"number": 12, "title": "crit-early",  "labels": [{"name": "rabbit-managed"}, {"name": "feature:rabbit-auto-evolve"}, {"name": "priority:critical"}], "body": "", "createdAt": "2026-05-30T08:00:00Z"},
    # low bucket
    {"number": 21, "title": "low-late",    "labels": [{"name": "rabbit-managed"}, {"name": "feature:rabbit-issue"}, {"name": "priority:low"}],      "body": "", "createdAt": "2026-05-01T20:00:00Z"},
    {"number": 22, "title": "low-early",   "labels": [{"name": "rabbit-managed"}, {"name": "feature:rabbit-issue"}, {"name": "priority:low"}],      "body": "", "createdAt": "2026-05-01T10:00:00Z"},
    # high bucket
    {"number": 31, "title": "high-late",   "labels": [{"name": "rabbit-managed"}, {"name": "feature:contract"}, {"name": "priority:high"}],     "body": "", "createdAt": "2026-05-15T18:00:00Z"},
    {"number": 32, "title": "high-early",  "labels": [{"name": "rabbit-managed"}, {"name": "feature:contract"}, {"name": "priority:high"}],     "body": "", "createdAt": "2026-05-15T06:00:00Z"},
    # medium bucket
    {"number": 51, "title": "med-late",    "labels": [{"name": "rabbit-managed"}, {"name": "feature:rabbit-auto-evolve"}, {"name": "priority:medium"}],   "body": "", "createdAt": "2026-05-20T16:00:00Z"},
    {"number": 52, "title": "med-early",   "labels": [{"name": "rabbit-managed"}, {"name": "feature:rabbit-auto-evolve"}, {"name": "priority:medium"}],   "body": "", "createdAt": "2026-05-20T04:00:00Z"},
]

rc, stdout, stderr = run_with_shim(FIXTURE)
if rc != 0:
    fail(f"B: expected exit 0 with shim, got {rc}; stderr={stderr!r}")
else:
    ok("B: invocation against gh-shim exited 0")

try:
    out = json.loads(stdout)
except json.JSONDecodeError as e:
    fail(f"B: stdout is not valid JSON ({e}); got {stdout!r}")
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

        # Verify within-bucket asc createdAt for the critical bucket
        # specifically (highest-priority bucket — most important to
        # surface first).
        crit = [i for i in out if any(lbl["name"] == "priority:critical" for lbl in i.get("labels", []))]
        if [i["title"] for i in crit] != ["crit-early", "crit-late"]:
            fail(f"B: critical-bucket order wrong: {[i['title'] for i in crit]}")
        else:
            ok("B: critical bucket sorted by createdAt asc")


# ---------------------------------------------------------------------------
# Scenario C — de-queue leak detector (issue #731, Inv 59)
# ---------------------------------------------------------------------------
# `fetch-queue.py --detect-leaks` surfaces OPEN issues that once entered the
# rabbit pipeline (carry a `filed-by:*` label) but have LOST the
# `rabbit-managed` label without being closed — the "de-queue" leak. The
# detector queries open issues via `gh` and emits a deterministic JSON object
# {"leaks": [...]} so a leaked issue is re-surfaced for re-convergence rather
# than lost. Issues that still carry `rabbit-managed`, or that never carried a
# `filed-by:*` label (never rabbit-managed), are NOT leaks.
LEAK_FIXTURE = [
    # LEAK: open, filed-by:loop provenance, but rabbit-managed was removed.
    {"number": 336, "title": "de-queued-loop", "labels": [{"name": "enhancement"}, {"name": "filed-by:loop"}, {"name": "priority:high"}], "body": "", "createdAt": "2026-06-01T00:00:00Z"},
    # LEAK: open, filed-by:human provenance, rabbit-managed removed.
    {"number": 677, "title": "de-queued-human", "labels": [{"name": "bug"}, {"name": "filed-by:human"}], "body": "", "createdAt": "2026-05-20T00:00:00Z"},
    # NOT a leak: still carries rabbit-managed.
    {"number": 500, "title": "still-queued", "labels": [{"name": "rabbit-managed"}, {"name": "filed-by:loop"}, {"name": "priority:low"}], "body": "", "createdAt": "2026-05-25T00:00:00Z"},
    # NOT a leak: never entered the rabbit pipeline (no filed-by:*, no managed).
    {"number": 900, "title": "unrelated", "labels": [{"name": "question"}], "body": "", "createdAt": "2026-05-26T00:00:00Z"},
]

rc, stdout, stderr = run_with_shim(LEAK_FIXTURE, ["--detect-leaks"])
if rc != 0:
    fail(f"C: --detect-leaks should exit 0 with shim, got {rc}; stderr={stderr!r}")
else:
    ok("C: --detect-leaks exited 0")

try:
    result = json.loads(stdout)
except json.JSONDecodeError as e:
    fail(f"C: --detect-leaks stdout is not valid JSON ({e}); got {stdout!r}")
    result = None

if result is not None:
    if not isinstance(result, dict) or "leaks" not in result:
        fail(f"C: expected JSON object with 'leaks' key, got {result!r}")
    else:
        leaked_numbers = {item.get("number") for item in result["leaks"]}
        if leaked_numbers != {336, 677}:
            fail(f"C: expected leaks {{336, 677}}, got {leaked_numbers}")
        else:
            ok("C: leak detector surfaces exactly the de-queued open issues")


# ---------------------------------------------------------------------------
# Scenario D — actionability-based selection (Inv 2 / #758, coexistence
# step 1 of #753: retire rabbit-managed).
# ---------------------------------------------------------------------------
# The queue is OPEN issues with BOTH a valid `feature:` label AND a valid
# `priority:` label — NOT keyed on `rabbit-managed`. This fixture mixes:
#   - actionable issues that DO carry rabbit-managed (still tolerated)
#   - an actionable issue with feature:+priority: but NO rabbit-managed
#     (must STILL be selected — proves label-independence)
#   - issues that must be EXCLUDED because they lack a feature: or a valid
#     priority: label, or are not actionable at all.
ACTION_FIXTURE = [
    # SELECTED: feature:+priority:, still carries rabbit-managed (coexistence).
    {"number": 100, "title": "managed-actionable", "labels": [{"name": "rabbit-managed"}, {"name": "feature:rabbit-auto-evolve"}, {"name": "priority:high"}], "body": "", "createdAt": "2026-05-10T00:00:00Z"},
    # SELECTED: feature:+priority:, NO rabbit-managed — label-independence.
    {"number": 101, "title": "unmanaged-actionable", "labels": [{"name": "feature:rabbit-issue"}, {"name": "priority:critical"}], "body": "", "createdAt": "2026-05-11T00:00:00Z"},
    # EXCLUDED: has rabbit-managed + priority but NO feature: label.
    {"number": 102, "title": "no-feature", "labels": [{"name": "rabbit-managed"}, {"name": "priority:medium"}], "body": "", "createdAt": "2026-05-12T00:00:00Z"},
    # EXCLUDED: has rabbit-managed + feature: but NO priority: label.
    {"number": 103, "title": "no-priority", "labels": [{"name": "rabbit-managed"}, {"name": "feature:contract"}], "body": "", "createdAt": "2026-05-13T00:00:00Z"},
    # EXCLUDED: has feature: but an UNRECOGNIZED priority value (not valid).
    {"number": 104, "title": "bad-priority", "labels": [{"name": "feature:contract"}, {"name": "priority:someday"}], "body": "", "createdAt": "2026-05-14T00:00:00Z"},
    # EXCLUDED: neither feature: nor priority: (unrelated human issue).
    {"number": 105, "title": "unrelated", "labels": [{"name": "question"}], "body": "", "createdAt": "2026-05-15T00:00:00Z"},
]

rc, stdout, stderr = run_with_shim(ACTION_FIXTURE)
if rc != 0:
    fail(f"D: expected exit 0 with shim, got {rc}; stderr={stderr!r}")
else:
    ok("D: actionability invocation exited 0")

try:
    selected = json.loads(stdout)
except json.JSONDecodeError as e:
    fail(f"D: stdout is not valid JSON ({e}); got {stdout!r}")
    selected = None

if selected is not None:
    if not isinstance(selected, list):
        fail(f"D: expected JSON array, got {type(selected).__name__}")
    else:
        nums = {i.get("number") for i in selected}
        if nums != {100, 101}:
            fail(f"D: expected selected {{100, 101}} (actionable open issues, "
                 f"label-independent), got {nums}")
        else:
            ok("D: selects exactly the actionable (feature:+valid priority:) "
               "issues, including the one with NO rabbit-managed label")
        # Explicit label-independence assertion: the unmanaged actionable
        # issue (101) carries no rabbit-managed label yet IS selected.
        unmanaged = next((i for i in selected if i.get("number") == 101), None)
        if unmanaged is None:
            fail("D: actionable issue 101 (no rabbit-managed) was NOT selected "
                 "— selection is wrongly keyed on rabbit-managed")
        elif any(l.get("name") == "rabbit-managed" for l in unmanaged.get("labels", [])):
            fail("D: fixture invariant broken — issue 101 should not carry "
                 "rabbit-managed")
        else:
            ok("D: label-independence — actionable issue without rabbit-managed "
               "is selected (coexistence step 1 of #753)")
        # Excluded issues must NOT leak in.
        for n in (102, 103, 104, 105):
            if n in nums:
                fail(f"D: non-actionable issue {n} should NOT be selected")
        if not (nums & {102, 103, 104, 105}):
            ok("D: issues missing a feature: or valid priority: label are excluded")


sys.exit(FAIL)
