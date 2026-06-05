#!/usr/bin/env python3
"""test-reconcile-labels.py — e2e tests for scripts/reconcile-labels.py (Inv 55).

The reconcile mirrors the dispatch-journal LIVE set (the union of issue numbers
whose journal status is `dispatched` or `pr_open`, computed by reusing
status-report.py's live-set logic) onto the sanctioned GitHub `in-progress`
category label:

  A) --help smoke test — exit 0 and recognizable usage text.
  B) Add/strip sets — a journal mixing dispatched/pr_open/completed/closed plus
     a pre-existing stale `in-progress` label yields exactly:
       ADD    `in-progress` to live-set OPEN issues lacking it.
       STRIP  `in-progress` from labelled OPEN issues not in the live set.
  C) Idempotent — a second run against the now-reconciled GitHub state makes
     NO add/remove edits.
  D) Stale-label self-heal — an issue carrying `in-progress` whose journal
     entry is `completed` (or absent) is STRIPPED on the next tick.
  E) Graceful on gh failure — a `gh issue edit` that exits non-zero is logged
     but does NOT crash the reconcile (exit 0) and the other edits still apply.
  F) Empty-journal no-op — no journal => empty live set => no adds; only strips
     of any pre-existing label, and a clean no-op when none.
  G) ensure_labels is invoked — the rabbit-issue label bootstrap runs (a
     `gh label create in-progress` call is recorded) before stamping.

The script is run as a subprocess so the on-PATH `gh` shim is honored. The
shim records every gh invocation to a log file and answers `issue list` /
`issue view` from a fixture file; `issue edit` and `label create` are recorded
as no-ops (or forced to fail for scenario E).
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "reconcile-labels.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# A gh shim that:
#   - records its full argv (one JSON array per line) to $GH_LOG.
#   - `issue list ...`  -> emits $GH_LIST_FIXTURE (the open issues carrying the
#     label) as JSON on stdout.
#   - `issue view <N> ...` -> emits the per-issue object from $GH_VIEW_FIXTURE
#     (a JSON map of "number" -> object) on stdout.
#   - `label create ...` / `issue edit ...` -> exit 0 (recorded only), UNLESS
#     $GH_FAIL_EDIT_ISSUE matches the edited issue number, then exit 1.
SHIM = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["GH_LOG"], "a") as f:
    f.write(json.dumps(argv) + "\n")

def arg_after(flag):
    return argv[argv.index(flag) + 1] if flag in argv else None

if len(argv) >= 2 and argv[0] == "issue" and argv[1] == "list":
    with open(os.environ["GH_LIST_FIXTURE"]) as f:
        sys.stdout.write(f.read())
    sys.exit(0)

if len(argv) >= 2 and argv[0] == "issue" and argv[1] == "view":
    num = argv[2]
    with open(os.environ["GH_VIEW_FIXTURE"]) as f:
        views = json.load(f)
    obj = views.get(str(num))
    if obj is None:
        sys.stderr.write("no such issue\n")
        sys.exit(1)
    sys.stdout.write(json.dumps(obj))
    sys.exit(0)

if len(argv) >= 2 and argv[0] == "issue" and argv[1] == "edit":
    num = argv[2]
    if os.environ.get("GH_FAIL_EDIT_ISSUE") == str(num):
        sys.stderr.write("gh: simulated edit failure\n")
        sys.exit(1)
    sys.exit(0)

if len(argv) >= 1 and argv[0] == "label":
    sys.exit(0)

# default: succeed quietly
sys.exit(0)
'''


def run(journal, list_fixture, view_fixture, fail_edit_issue=None):
    """Run reconcile-labels.py with a PATH-resident gh shim.

    Returns (returncode, stdout, stderr, gh_calls) where gh_calls is the list
    of recorded argv lists.
    """
    with tempfile.TemporaryDirectory() as tmp:
        # state dir + journal
        state_dir = os.path.join(tmp, ".rabbit")
        os.makedirs(state_dir)
        state = {"schema_version": "1.4.0", "dispatch_journal": journal}
        with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
            json.dump(state, f)

        gh_log = os.path.join(tmp, "gh.log")
        list_path = os.path.join(tmp, "list.json")
        view_path = os.path.join(tmp, "view.json")
        with open(list_path, "w") as f:
            json.dump(list_fixture, f)
        with open(view_path, "w") as f:
            json.dump(view_fixture, f)

        shim_dir = os.path.join(tmp, "bin")
        os.makedirs(shim_dir)
        shim_path = os.path.join(shim_dir, "gh")
        with open(shim_path, "w") as f:
            f.write(SHIM)
        os.chmod(shim_path, stat.S_IRWXU)

        env = os.environ.copy()
        env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
        env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
        env["RABBIT_ISSUE_REPO"] = "owner/repo"
        env["GH_LOG"] = gh_log
        env["GH_LIST_FIXTURE"] = list_path
        env["GH_VIEW_FIXTURE"] = view_path
        if fail_edit_issue is not None:
            env["GH_FAIL_EDIT_ISSUE"] = str(fail_edit_issue)

        proc = subprocess.run(
            [sys.executable, SCRIPT],
            capture_output=True, text=True, env=env,
        )
        calls = []
        if os.path.exists(gh_log):
            with open(gh_log) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        calls.append(json.loads(line))
        return proc.returncode, proc.stdout, proc.stderr, calls


def _entry(issue, status):
    return {"issue": issue, "feature": "f", "shape": "single", "status": status}


def _tick(*entries):
    return {"started_at": "2026-06-05T00:00:00Z", "entries": list(entries)}


def edits_for(calls):
    """Return {issue_number: set(of '--add-label X' / '--remove-label X')}."""
    out = {}
    for c in calls:
        if len(c) >= 3 and c[0] == "issue" and c[1] == "edit":
            num = int(c[2])
            adds = {c[i + 1] for i, a in enumerate(c) if a == "--add-label"}
            rems = {c[i + 1] for i, a in enumerate(c) if a == "--remove-label"}
            out.setdefault(num, {"add": set(), "remove": set()})
            out[num]["add"] |= adds
            out[num]["remove"] |= rems
    return out


def label_creates(calls):
    return [c for c in calls if len(c) >= 2 and c[0] == "label" and c[1] == "create"]


LABEL = "in-progress"

# ---------------------------------------------------------------------------
# Scenario A — --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run([sys.executable, SCRIPT, "--help"],
                      capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"A: --help should exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("A: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail("A: --help output should contain 'usage'")
else:
    ok("A: --help output contains 'usage'")


# ---------------------------------------------------------------------------
# Scenario B — add/strip sets (mixed journal + pre-existing stale label)
# ---------------------------------------------------------------------------
# Journal: #1 dispatched (live), #2 pr_open (live), #3 completed (not live),
#          #4 aborted (not live).
journal = {"t1": _tick(_entry(1, "dispatched"), _entry(2, "pr_open"),
                       _entry(3, "completed"), _entry(4, "aborted"))}
# GitHub currently has #2 and #9 carrying the label (open). #9 is a STALE
# leftover not in the journal at all -> must be stripped. #2 already has it ->
# no add needed. #1 is live + open + missing label -> add.
list_fixture = [{"number": 2}, {"number": 9}]
view_fixture = {
    "1": {"number": 1, "state": "OPEN", "labels": [{"name": "feature:f"}]},
    "2": {"number": 2, "state": "OPEN", "labels": [{"name": LABEL}]},
}
rc, out, err, calls = run(journal, list_fixture, view_fixture)
if rc != 0:
    fail(f"B: reconcile should exit 0, got {rc}; stderr={err!r}")
else:
    ok("B: reconcile exited 0")
e = edits_for(calls)
if e.get(1, {}).get("add") == {LABEL} and not e.get(1, {}).get("remove"):
    ok("B: #1 (live, missing) gets --add-label in-progress")
else:
    fail(f"B: #1 should be add-only; got {e.get(1)}")
if 2 not in e:
    ok("B: #2 (live, already labelled) is not edited (idempotent add)")
else:
    fail(f"B: #2 should not be edited; got {e.get(2)}")
if e.get(9, {}).get("remove") == {LABEL} and not e.get(9, {}).get("add"):
    ok("B: #9 (stale, not live) gets --remove-label in-progress")
else:
    fail(f"B: #9 should be remove-only; got {e.get(9)}")
# #3/#4 are completed/aborted and not currently labelled -> no edits.
if 3 not in e and 4 not in e:
    ok("B: completed/aborted unlabelled issues are not edited")
else:
    fail(f"B: #3/#4 should not be edited; got 3={e.get(3)} 4={e.get(4)}")


# ---------------------------------------------------------------------------
# Scenario C — idempotent on re-run (GitHub already reconciled)
# ---------------------------------------------------------------------------
# Now #1 and #2 both carry the label; #9 stripped. live = {1, 2}.
list_fixture2 = [{"number": 1}, {"number": 2}]
view_fixture2 = {
    "1": {"number": 1, "state": "OPEN", "labels": [{"name": LABEL}]},
    "2": {"number": 2, "state": "OPEN", "labels": [{"name": LABEL}]},
}
rc, out, err, calls = run(journal, list_fixture2, view_fixture2)
if rc != 0:
    fail(f"C: reconcile should exit 0, got {rc}")
else:
    ok("C: reconcile exited 0")
e = edits_for(calls)
if not e:
    ok("C: no add/remove edits on an already-reconciled state (idempotent)")
else:
    fail(f"C: expected no edits, got {e}")


# ---------------------------------------------------------------------------
# Scenario D — stale-label self-heal (completed entry still labelled)
# ---------------------------------------------------------------------------
# #5 completed but GitHub still carries the label from a crashed tick.
journal_d = {"t1": _tick(_entry(5, "completed"))}
list_fixture_d = [{"number": 5}]
view_fixture_d = {
    "5": {"number": 5, "state": "OPEN", "labels": [{"name": LABEL}]},
}
rc, out, err, calls = run(journal_d, list_fixture_d, view_fixture_d)
e = edits_for(calls)
if rc == 0 and e.get(5, {}).get("remove") == {LABEL}:
    ok("D: stale label on a completed issue is stripped next tick")
else:
    fail(f"D: #5 should be stripped; rc={rc} edits={e}")


# ---------------------------------------------------------------------------
# Scenario E — graceful on gh failure
# ---------------------------------------------------------------------------
# live = {6, 7}; both open + missing label. Force the edit of #6 to FAIL.
journal_e = {"t1": _tick(_entry(6, "dispatched"), _entry(7, "pr_open"))}
list_fixture_e = []
view_fixture_e = {
    "6": {"number": 6, "state": "OPEN", "labels": []},
    "7": {"number": 7, "state": "OPEN", "labels": []},
}
rc, out, err, calls = run(journal_e, list_fixture_e, view_fixture_e,
                          fail_edit_issue=6)
e = edits_for(calls)
if rc == 0:
    ok("E: reconcile exits 0 despite a gh edit failure")
else:
    fail(f"E: reconcile should not crash on gh failure; rc={rc} stderr={err!r}")
# The other issue's add still got attempted.
if e.get(7, {}).get("add") == {LABEL}:
    ok("E: a failing edit does not abort the remaining reconcile")
else:
    fail(f"E: #7 should still be add-attempted; got {e.get(7)}")


# ---------------------------------------------------------------------------
# Scenario F — empty journal: no adds, strips stale, clean no-op otherwise
# ---------------------------------------------------------------------------
# F1: empty journal, one stale labelled issue -> strip it.
rc, out, err, calls = run({}, [{"number": 8}],
                          {"8": {"number": 8, "state": "OPEN",
                                 "labels": [{"name": LABEL}]}})
e = edits_for(calls)
if rc == 0 and e.get(8, {}).get("remove") == {LABEL} and not e.get(8, {}).get("add"):
    ok("F1: empty journal strips a stale label (no adds)")
else:
    fail(f"F1: #8 should be stripped, no adds; rc={rc} edits={e}")
# F2: empty journal, nothing labelled -> clean no-op.
rc, out, err, calls = run({}, [], {})
e = edits_for(calls)
if rc == 0 and not e:
    ok("F2: empty journal + nothing labelled is a clean no-op")
else:
    fail(f"F2: expected clean no-op; rc={rc} edits={e}")


# ---------------------------------------------------------------------------
# Scenario G — ensure_labels bootstrap runs (label create attempted)
# ---------------------------------------------------------------------------
rc, out, err, calls = run(
    {"t1": _tick(_entry(10, "dispatched"))},
    [],
    {"10": {"number": 10, "state": "OPEN", "labels": []}})
creates = label_creates(calls)
if creates and any(LABEL in c for c in creates):
    ok("G: ensure_labels bootstraps the in-progress label before stamping")
else:
    fail(f"G: expected a `gh label create in-progress` call; got {creates}")


print()
if FAIL:
    print("RESULT: FAIL", file=sys.stderr)
    sys.exit(1)
print("RESULT: PASS")
sys.exit(0)
