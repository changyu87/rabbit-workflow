#!/usr/bin/env python3
"""test-exclude-decomposition-parents.py — e2e tests for issue #948.

A recorded DECOMPOSITION PARENT must NEVER be surfaced as a dispatchable
work item by the plan phase: it carries no own code change and auto-closes
via close-decomposed-parents.py (Inv 53) once all children close. Before
this fix the parent kept reappearing at the bottom of `selection_order`
every tick, forcing the dispatcher to recognize and skip it manually — a
convergence/safety hole.

This exercises the FULL triage -> plan pipe end to end:

  triage-issue.py <N>  (real, with a PATH-resident gh shim)  -> triage object
  plan-batch.py        (real)                                -> dispatch plan

and asserts:

  - PRIMARY (native rollup): an open issue whose GitHub-native sub-issue
    rollup shows it HAS children (`sub_issues_summary.total > 0`) is a
    decomposition parent and is EXCLUDED from selection_order,
    dispatch_shapes, and cross_scope_items.
  - COEXISTENCE (state map): an open issue listed as a key in the
    `decomposition_parents` state map but with NO native sub-issues yet
    (`total == 0`) is ALSO excluded.
  - NO REGRESSION: an ordinary single-feature issue (no children, not in the
    map) is STILL selected and shaped; a CHILD issue (it has a PARENT link
    but `total == 0` — no children of its own) is STILL selected and shaped.

The native-rollup signal comes from `gh api repos/<slug>/issues/<n>` ->
`sub_issues_summary`, the same authoritative source #940 wired into
close-decomposed-parents.py. The coexistence signal comes from the
`decomposition_parents` map in <state_dir>/auto-evolve-state.json
(RABBIT_AUTO_EVOLVE_STATE_DIR test seam).
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(HERE, ".."))
TRIAGE_SCRIPT = os.path.join(FEATURE_DIR, "scripts", "triage-issue.py")
PLAN_SCRIPT = os.path.join(FEATURE_DIR, "scripts", "plan-batch.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# A gh shim dispatching the three calls triage-issue.py makes:
#   gh issue view <N> --repo ... --json ...   (per-issue metadata)
#   gh issue list  --state closed ...         (rule-3 duplicate check)
#   gh api repos/<slug>/issues/<N>            (native sub-issue rollup; #948)
# The view/list payloads come from a baked table; the api summaries come from
# GH_SUMMARIES so a parent with sub-issues can be modeled per-issue.
GH_SHIM = r"""#!/usr/bin/env python3
import json, os, re, sys
VIEWS = json.loads(os.environ["GH_VIEWS"])
SUMMARIES = json.loads(os.environ["GH_SUMMARIES"])
argv = sys.argv[1:]
if argv[:2] == ["issue", "view"]:
    num = argv[2]
    sys.stdout.write(VIEWS.get(num, "{}"))
    sys.exit(0)
if argv[:2] == ["issue", "list"]:
    sys.stdout.write("[]")
    sys.exit(0)
if argv[:1] == ["api"]:
    m = re.match(r"repos/[^/]+/[^/]+/issues/(\d+)$", argv[1])
    if m:
        num = m.group(1)
        summ = SUMMARIES.get(num, {"total": 0, "completed": 0})
        sys.stdout.write(json.dumps(
            {"number": int(num), "sub_issues_summary": summ}))
        sys.exit(0)
    sys.exit(3)
sys.stderr.write("gh-shim: unrecognized: %s\n" % " ".join(argv))
sys.exit(2)
"""


def _make_feature(repo_root, name):
    fdir = os.path.join(repo_root, ".claude", "features", name)
    os.makedirs(os.path.join(fdir, "docs"), exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({
            "name": name, "version": "0.1.0",
            "owner": "rabbit-workflow team", "status": "active",
            "deprecation_criterion": "n/a",
        }, f)
    with open(os.path.join(fdir, "docs", "spec.md"), "w") as f:
        f.write("---\nfeature: %s\nversion: 0.1.0\n"
                "owner: rabbit-workflow team\n---\n\n# Spec\n\nBody.\n" % name)


def _view(num, feature, title, body=""):
    return json.dumps({
        "number": num,
        "title": title,
        "body": body,
        "labels": [{"name": "feature:" + feature},
                   {"name": "priority:medium"}],
        "state": "OPEN",
        "stateReason": "",
        "comments": [],
        "createdAt": "2026-06-01T00:00:00Z",
    })


def run_plan(triage_objs):
    return subprocess.run(
        [sys.executable, PLAN_SCRIPT, "--max-parallel", "4"],
        input=json.dumps(triage_objs),
        capture_output=True, text=True,
    )


with tempfile.TemporaryDirectory() as td:
    repo_root = os.path.join(td, "repo")
    shim_dir = os.path.join(td, "bin")
    state_dir = os.path.join(repo_root, ".rabbit")
    os.makedirs(shim_dir)
    os.makedirs(state_dir)
    _make_feature(repo_root, "feat-a")
    _make_feature(repo_root, "feat-b")

    # Issues under test:
    #   935 — decomposition PARENT (native rollup total>0)  -> EXCLUDE
    #   936 — decomposition PARENT only in the state map     -> EXCLUDE
    #          (coexistence: native total==0, listed in decomposition_parents)
    #   942 — CHILD (has a parent link, but total==0)        -> INCLUDE
    #   950 — ordinary single-feature issue                  -> INCLUDE
    views = {
        "935": _view(935, "feat-a", "decomposed parent A"),
        "936": _view(936, "feat-a", "decomposed parent B"),
        "942": _view(942, "feat-b", "child sub-issue",
                     body="Sub-issue of parent #935."),
        "950": _view(950, "feat-b", "ordinary single-feature work"),
    }
    # Native rollups: 935 HAS children; 936/942/950 have none of their own.
    summaries = {
        "935": {"total": 6, "completed": 1},
        "936": {"total": 0, "completed": 0},
        "942": {"total": 0, "completed": 0},
        "950": {"total": 0, "completed": 0},
    }

    # Coexistence state map: 936 recorded as a parent (no native children yet).
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump({
            "schema_version": "1.4.0",
            "updated_at": "2026-06-04T00:00:00Z",
            "queue": [],
            "decomposition_parents": {"936": [960, 961]},
        }, f)

    shim_path = os.path.join(shim_dir, "gh")
    with open(shim_path, "w") as f:
        f.write(GH_SHIM)
    os.chmod(shim_path, os.stat(shim_path).st_mode | stat.S_IEXEC |
             stat.S_IXGRP | stat.S_IXOTH)

    env_views = json.dumps(views)
    triage_objs = []
    for num in (935, 936, 942, 950):
        env = os.environ.copy()
        env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
        env["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
        env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
        env["GH_VIEWS"] = env_views
        env["GH_SUMMARIES"] = json.dumps(summaries)
        proc = subprocess.run(
            [sys.executable, TRIAGE_SCRIPT, str(num)],
            capture_output=True, text=True, env=env, cwd=repo_root,
        )
        if proc.returncode != 0:
            fail("triage #%d exited %d: %s" % (num, proc.returncode,
                                               proc.stderr))
            continue
        try:
            triage_objs.append(json.loads(proc.stdout))
        except json.JSONDecodeError as e:
            fail("triage #%d stdout not JSON (%s): %r" % (num, e, proc.stdout))

    # Every triaged issue is decision=work (so absence from the plan is the
    # exclusion under test, not a defer/close upstream).
    for obj in triage_objs:
        if obj.get("decision") != "work":
            fail("issue #%s triaged as %r, expected work (test premise)" % (
                obj.get("issue"), obj.get("decision")))

    plan_proc = run_plan(triage_objs)
    if plan_proc.returncode != 0:
        fail("plan-batch exited %d: %s" % (plan_proc.returncode,
                                           plan_proc.stderr))
        plan = {}
    else:
        ok("triage -> plan pipe ran cleanly")
        plan = json.loads(plan_proc.stdout)

    selection = plan.get("selection_order", [])
    shapes = plan.get("dispatch_shapes", {})
    cross = plan.get("cross_scope_items", [])

    # PRIMARY — native-rollup parent 935 excluded everywhere.
    if 935 in selection:
        fail("parent 935 (native rollup total>0) still in selection_order")
    else:
        ok("parent 935 (native rollup total>0) excluded from selection_order")
    if "935" in shapes:
        fail("parent 935 still in dispatch_shapes")
    else:
        ok("parent 935 excluded from dispatch_shapes")
    if 935 in cross:
        fail("parent 935 still in cross_scope_items")
    else:
        ok("parent 935 excluded from cross_scope_items")

    # COEXISTENCE — state-map parent 936 excluded.
    if 936 in selection:
        fail("parent 936 (decomposition_parents map) still in selection_order")
    else:
        ok("parent 936 (state-map coexistence) excluded from selection_order")
    if "936" in shapes:
        fail("parent 936 still in dispatch_shapes")
    else:
        ok("parent 936 excluded from dispatch_shapes")

    # NO REGRESSION — child 942 (has a parent, total==0) still dispatched.
    if 942 not in selection:
        fail("child 942 (total==0) was wrongly excluded from selection_order")
    else:
        ok("child 942 (has parent, total==0) still selected")
    if "942" not in shapes:
        fail("child 942 missing from dispatch_shapes")
    else:
        ok("child 942 still shaped")

    # NO REGRESSION — ordinary issue 950 still dispatched and shaped.
    if 950 not in selection:
        fail("ordinary issue 950 was wrongly excluded from selection_order")
    else:
        ok("ordinary issue 950 still selected")
    if shapes.get("950") != "parallel-per-feature":
        fail("ordinary issue 950 shape=%r, expected parallel-per-feature" %
             shapes.get("950"))
    else:
        ok("ordinary issue 950 shaped parallel-per-feature")


sys.exit(FAIL)
