#!/usr/bin/env python3
"""test-triage-priority-flow.py — e2e: triage-issue.py priority flows into
plan-batch.py ordering (issue #484).

The #479 priority-primary ordering fix in plan-batch.py reads each item's
`priority` field. Before #484, triage-issue.py never emitted `priority`, so
every triage record sorted at the no-priority rank and the priority-primary
ordering silently collapsed to the contract-touch-only tiebreak — a
low-priority CONTRACT item would lead a high-priority NON-contract item
(the barrier-overrides-priority bug, still effective).

This test exercises the FULL pipe with no hand-authored priority values:
  1. Run scripts/triage-issue.py (via a gh shim) on a high-priority
     non-contract issue and on a low-priority contract issue.
  2. Collect the two emitted triage records into a JSON array.
  3. Pipe that array into scripts/plan-batch.py.
  4. Assert the high-priority non-contract issue leads selection_order and
     that barrier_first is EMPTY (the low contract item does NOT jump the
     priority tier). If triage drops `priority`, both items would tie at
     no-priority rank and the contract item would lead barrier_first —
     so this test FAILS without the #484 fix.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TRIAGE = os.path.normpath(os.path.join(HERE, "..", "scripts", "triage-issue.py"))
PLAN = os.path.normpath(os.path.join(HERE, "..", "scripts", "plan-batch.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_shim(shim_dir, view_responses, list_response):
    """Write a `gh` shim that dispatches by subcommand (mirrors
    test-triage-rules.py)."""
    for num, payload in view_responses.items():
        with open(os.path.join(shim_dir, f"view-{num}.json"), "w") as f:
            f.write(payload)
    with open(os.path.join(shim_dir, "list.json"), "w") as f:
        f.write(list_response)
    shim_path = os.path.join(shim_dir, "gh")
    with open(shim_path, "w") as f:
        f.write("#!/bin/sh\n")
        f.write('sub="$1"; verb="$2"\n')
        f.write('if [ "$sub" = "issue" ] && [ "$verb" = "view" ]; then\n')
        f.write('  num="$3"\n')
        f.write(f'  cat "{shim_dir}/view-${{num}}.json"\n')
        f.write('  exit 0\n')
        f.write('elif [ "$sub" = "issue" ] && [ "$verb" = "list" ]; then\n')
        f.write(f'  cat "{shim_dir}/list.json"\n')
        f.write('  exit 0\n')
        f.write('fi\n')
        f.write('echo "gh-shim: unrecognized: $@" >&2\n')
        f.write('exit 2\n')
    os.chmod(shim_path, stat.S_IRWXU)
    return shim_path


def make_feature(repo_root, feature_name):
    fdir = os.path.join(repo_root, ".claude", "features", feature_name)
    os.makedirs(os.path.join(fdir, "specs"), exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({
            "name": feature_name,
            "version": "0.1.0",
            "owner": "rabbit-workflow team",
            "status": "active",
            "deprecation_criterion": "n/a",
        }, f)
    with open(os.path.join(fdir, "specs", "spec.md"), "w") as f:
        f.write("---\nfeature: %s\nversion: 0.1.0\n"
                "owner: rabbit-workflow team\n---\n\n# Spec\n\nBody.\n"
                % feature_name)


def run_triage(repo_root, issue_num, shim_dir):
    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
    return subprocess.run(
        [sys.executable, TRIAGE, str(issue_num)],
        capture_output=True, text=True, env=env, cwd=repo_root,
    )


def run_plan(items):
    return subprocess.run(
        [sys.executable, PLAN],
        input=json.dumps(items), capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# Build a fake repo with two features and triage two issues:
#   #700  feature:prio-hi  priority:high  (NON-contract)
#   #701  feature:contract priority:low   (contract-touch)
# Acceptance (#484): high non-contract must sort before low contract.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "prio-hi")
    make_feature(repo_root, "contract")

    issue_hi = json.dumps({
        "number": 700,
        "title": "Add new behavior to prio-hi",
        "body": "Implement this fresh behavior.",
        "labels": [
            {"name": "rabbit-managed"},
            {"name": "feature:prio-hi"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    issue_lo = json.dumps({
        "number": 701,
        "title": "Tweak the contract surface",
        "body": "A small contract touch.",
        "labels": [
            {"name": "rabbit-managed"},
            {"name": "feature:contract"},
            {"name": "priority:low"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"700": issue_hi, "701": issue_lo}, list_payload)

    records = []
    abort = False
    for num in (700, 701):
        proc = run_triage(repo_root, num, shim_dir)
        if proc.returncode != 0:
            fail(f"flow: triage #{num} exit {proc.returncode}; "
                 f"stderr={proc.stderr!r}")
            abort = True
            break
        try:
            rec = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            fail(f"flow: triage #{num} bad JSON ({e}); stdout={proc.stdout!r}")
            abort = True
            break
        # Each triage record MUST carry the priority field (issue #484).
        if "priority" not in rec:
            fail(f"flow: triage #{num} record omits 'priority' key; "
                 f"record={rec!r}")
            abort = True
            break
        records.append(rec)

    if not abort:
        # Sanity: the high issue's priority arrived as "high".
        hi_rec = next(r for r in records if r["issue"] == 700)
        lo_rec = next(r for r in records if r["issue"] == 701)
        if hi_rec.get("priority") != "high":
            fail(f"flow: #700 priority={hi_rec.get('priority')!r}, want 'high'")
        elif lo_rec.get("priority") != "low":
            fail(f"flow: #701 priority={lo_rec.get('priority')!r}, want 'low'")
        else:
            ok("flow: triage emits priority high/low onto the records")

        plan_proc = run_plan(records)
        if plan_proc.returncode != 0:
            fail(f"flow: plan-batch exit {plan_proc.returncode}; "
                 f"stderr={plan_proc.stderr!r}")
        else:
            try:
                out = json.loads(plan_proc.stdout)
            except json.JSONDecodeError as e:
                fail(f"flow: plan-batch bad JSON ({e}); "
                     f"stdout={plan_proc.stdout!r}")
            else:
                sel = out.get("selection_order")
                bar = out.get("barrier_first")
                if sel != [700, 701]:
                    fail(f"flow: selection_order={sel!r}, want [700, 701] "
                         f"(high non-contract MUST lead low contract — the "
                         f"#484 dead-letter symptom is sel=[701, 700])")
                elif bar != []:
                    fail(f"flow: barrier_first={bar!r}, want [] (the low "
                         f"contract item must NOT jump the priority tier)")
                else:
                    ok("flow: high non-contract leads low contract end-to-end; "
                       "barrier_first empty (priority field flows through)")


sys.exit(FAIL)
