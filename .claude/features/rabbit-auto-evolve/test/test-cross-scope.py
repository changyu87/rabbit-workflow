#!/usr/bin/env python3
"""test-cross-scope.py — e2e tests for cross-scope detection + routing (Inv 56,
issue #433).

Two surfaces are exercised end-to-end as subprocesses (no live network, no
in-process imports):

  - triage-issue.py — emits `cross_scope` (bool) and `cross_scope_features`
    (sorted feature set) on every triage record. `cross_scope` is true when
    the issue body implicates >1 feature (the `features` set spans >=2 dirs)
    OR a cross-scope phrase ("repo-wide", "across all features", ...) appears;
    false for an ordinary single-feature body with no phrase.
  - plan-batch.py — a `cross_scope` work item is NEVER shaped
    `parallel-per-feature`; it gets `multi-subagent-barrier` (below the
    decompose threshold) or `decomposition` (at/above it), and is listed under
    the `cross_scope_items` output key.

A `gh` shim on $PATH under a tempdir serves the triage fixture responses.
"""

import json
import os
import shutil
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


# ---------------------------------------------------------------------------
# Helpers: fake repo + gh shim (mirrors test-triage-rules.py).
# ---------------------------------------------------------------------------
def make_feature(repo_root, name):
    fdir = os.path.join(repo_root, ".claude", "features", name, "docs", "spec")
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(repo_root, ".claude", "features", name,
                           "feature.json"), "w") as f:
        json.dump({"name": name, "version": "0.1.0",
                   "owner": "rabbit-workflow team",
                   "status": "active", "deprecation_criterion": "n/a"}, f)
    with open(os.path.join(fdir, "spec.md"), "w") as f:
        f.write("---\nfeature: %s\nversion: 0.1.0\n"
                "owner: rabbit-workflow team\n---\n\n# Spec\n\nBody.\n" % name)


def write_shim(shim_dir, view_payload, list_payload="[]"):
    with open(os.path.join(shim_dir, "view.json"), "w") as f:
        f.write(view_payload)
    with open(os.path.join(shim_dir, "list.json"), "w") as f:
        f.write(list_payload)
    shim_path = os.path.join(shim_dir, "gh")
    with open(shim_path, "w") as f:
        f.write("#!/bin/sh\n")
        f.write('sub="$1"; verb="$2"\n')
        f.write('if [ "$sub" = "issue" ] && [ "$verb" = "view" ]; then\n')
        f.write(f'  cat "{shim_dir}/view.json"; exit 0\n')
        f.write('elif [ "$sub" = "issue" ] && [ "$verb" = "list" ]; then\n')
        f.write(f'  cat "{shim_dir}/list.json"; exit 0\n')
        f.write('fi\n')
        f.write('echo "gh-shim: unrecognized: $@" >&2; exit 2\n')
    os.chmod(shim_path, stat.S_IRWXU)


def run_triage(repo_root, issue_num, shim_dir):
    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
    return subprocess.run(
        [sys.executable, TRIAGE, str(issue_num)],
        capture_output=True, text=True, env=env, cwd=repo_root,
    )


def triage_record(label, repo_root, issue_num, shim_dir):
    proc = run_triage(repo_root, issue_num, shim_dir)
    if proc.returncode != 0:
        fail(f"{label}: triage exit {proc.returncode}; stderr={proc.stderr!r}")
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"{label}: bad JSON ({e}); stdout={proc.stdout!r}")
        return None


def run_plan(items, extra_args=None):
    args = [sys.executable, PLAN]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(
        args, input=json.dumps(items), capture_output=True, text=True,
    )


def plan_json(label, items, extra_args=None):
    proc = run_plan(items, extra_args)
    if proc.returncode != 0:
        fail(f"{label}: plan exit {proc.returncode}; stderr={proc.stderr!r}")
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"{label}: bad JSON ({e}); stdout={proc.stdout!r}")
        return None


# ===========================================================================
# TRIAGE — cross_scope detection
# ===========================================================================

# (1) Body referencing >=2 distinct .claude/features/<name>/ paths -> true.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    make_feature(repo_root, "rabbit-issue")
    make_feature(repo_root, "rabbit-meta")
    body = ("Repo sweep touching .claude/features/rabbit-issue/scripts/x.py "
            "and .claude/features/rabbit-meta/docs/spec.md in one pass.")
    issue_payload = json.dumps({
        "number": 4331, "title": "Cross-feature sweep", "body": body,
        "labels": [{"name": "feature:rabbit-auto-evolve"},
                   {"name": "priority:high"}, {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-multipath", repo_root, 4331, shim_dir)
    if r is not None:
        if r.get("cross_scope") is not True:
            fail(f"triage-multipath: cross_scope should be True for >=2 feature "
                 f"paths; got {r.get('cross_scope')!r}; record={r!r}")
        elif sorted(r.get("cross_scope_features") or []) != [
                "rabbit-auto-evolve", "rabbit-issue", "rabbit-meta"]:
            fail(f"triage-multipath: cross_scope_features should be the sorted "
                 f"3-feature set; got {r.get('cross_scope_features')!r}")
        else:
            ok("triage: >=2 feature paths -> cross_scope true + feature set")


# (2) Single-feature body with a 'repo-wide' phrase -> true (phrase signal).
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    issue_payload = json.dumps({
        "number": 4332, "title": "Repo-wide rename",
        "body": "This is a repo-wide change; rename the marker token "
                "everywhere.",
        "labels": [{"name": "feature:rabbit-auto-evolve"},
                   {"name": "priority:high"}, {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-phrase", repo_root, 4332, shim_dir)
    if r is not None:
        if r.get("cross_scope") is not True:
            fail(f"triage-phrase: 'repo-wide' phrase must set cross_scope true "
                 f"even with one feature dir; got {r.get('cross_scope')!r}")
        else:
            ok("triage: 'repo-wide' phrase -> cross_scope true")


# (2b) 'across all features' phrase -> true.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    issue_payload = json.dumps({
        "number": 4333, "title": "Sweep",
        "body": "Apply this consistently across all features.",
        "labels": [{"name": "feature:rabbit-auto-evolve"},
                   {"name": "priority:medium"}, {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-phrase2", repo_root, 4333, shim_dir)
    if r is not None and r.get("cross_scope") is not True:
        fail(f"triage-phrase2: 'across all features' must set cross_scope true; "
             f"got {r.get('cross_scope')!r}")
    elif r is not None:
        ok("triage: 'across all features' phrase -> cross_scope true")


# (2c) DECOMPOSITION SUB-ISSUE (issue #667): a single-feature sub-issue whose
#      ONLY cross-scope phrase ('repo-wide') appears on a PARENT-REFERENCE line
#      that QUOTES the parent's framing -> cross_scope FALSE. The body's own
#      scope touches exactly one feature dir. End-to-end: triage emits
#      cross_scope:false AND plan-batch shapes the record parallel-per-feature.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    body = (
        "Sub-issue of parent #420 (retire B/B terminology repo-wide).\n\n"
        "Scope: only this feature. Rename the marker token in "
        ".claude/features/rabbit-auto-evolve/scripts/triage-issue.py and add "
        "a test under .claude/features/rabbit-auto-evolve/test/."
    )
    issue_payload = json.dumps({
        "number": 6601, "title": "Retire B/B terminology in rabbit-auto-evolve",
        "body": body,
        "labels": [{"name": "feature:rabbit-auto-evolve"},
                   {"name": "priority:medium"}, {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-subissue", repo_root, 6601, shim_dir)
    if r is not None:
        if r.get("cross_scope") is not False:
            fail(f"triage-subissue: a single-feature decomposition sub-issue "
                 f"whose only 'repo-wide' phrase is on a parent-reference line "
                 f"must be cross_scope FALSE; got {r.get('cross_scope')!r}; "
                 f"record={r!r}")
        else:
            ok("triage: decomposition sub-issue (parent-quote 'repo-wide') -> "
               "cross_scope false")
            # End-to-end: the same triaged record must shape
            # parallel-per-feature (a genuine single-feature work item).
            out = plan_json("plan-subissue", [r])
            if out is not None:
                shape = out.get("dispatch_shapes", {}).get(str(r.get("issue")))
                if shape != "parallel-per-feature":
                    fail(f"plan-subissue: decomposition sub-issue must be shaped "
                         f"parallel-per-feature; got {shape!r}")
                elif out.get("cross_scope_items") != []:
                    fail(f"plan-subissue: a non-cross_scope sub-issue must NOT "
                         f"appear in cross_scope_items; got "
                         f"{out.get('cross_scope_items')!r}")
                else:
                    ok("plan: decomposition sub-issue -> parallel-per-feature "
                       "(not in cross_scope_items)")


# (2d) GENUINE repo-wide issue (issue #667 — preserve true detection): a bare
#      non-parent 'sweep every feature' instruction in the issue's OWN scope
#      STILL yields cross_scope TRUE even though one feature is labelled.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    body = (
        "Sweep every feature and rename the legacy token in each one. "
        "This must be applied across all features in a single pass."
    )
    issue_payload = json.dumps({
        "number": 6602, "title": "Repo-wide token rename",
        "body": body,
        "labels": [{"name": "feature:rabbit-auto-evolve"},
                   {"name": "priority:high"}, {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-genuine-bare", repo_root, 6602, shim_dir)
    if r is not None:
        if r.get("cross_scope") is not True:
            fail(f"triage-genuine-bare: a bare (non-parent) 'sweep every "
                 f"feature' / 'across all features' instruction MUST keep "
                 f"cross_scope true; got {r.get('cross_scope')!r}; record={r!r}")
        else:
            ok("triage: genuine bare 'sweep every feature' -> cross_scope true")


# (2e) GENUINE multi-feature issue (issue #667 — preserve true detection): the
#      issue's OWN body enumerates >=2 distinct feature paths OUTSIDE any
#      parent-reference line -> cross_scope TRUE, even alongside a parent
#      reference line. The parent-reference exclusion strips only the parent
#      line, not the body's own multi-feature enumeration.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    make_feature(repo_root, "rabbit-issue")
    make_feature(repo_root, "rabbit-meta")
    body = (
        "Part of #900 (umbrella cleanup).\n\n"
        "This sub-issue itself rewrites .claude/features/rabbit-issue/scripts/a.py "
        "and .claude/features/rabbit-meta/docs/spec.md together in one pass."
    )
    issue_payload = json.dumps({
        "number": 6603, "title": "Cross-feature rewrite",
        "body": body,
        "labels": [{"name": "feature:rabbit-auto-evolve"},
                   {"name": "priority:high"}, {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-genuine-multipath", repo_root, 6603, shim_dir)
    if r is not None:
        if r.get("cross_scope") is not True:
            fail(f"triage-genuine-multipath: the body's OWN >=2 distinct "
                 f"feature paths (outside the parent line) MUST keep "
                 f"cross_scope true; got {r.get('cross_scope')!r}; record={r!r}")
        else:
            ok("triage: genuine multi-feature body (with a parent line) -> "
               "cross_scope true")


# (3) Ordinary single-feature body, no phrase, no extra paths -> false.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    issue_payload = json.dumps({
        "number": 4334, "title": "Add a retry wrapper",
        "body": "Implement a small retry wrapper around the fetch helper.",
        "labels": [{"name": "feature:rabbit-auto-evolve"},
                   {"name": "priority:low"}, {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-single", repo_root, 4334, shim_dir)
    if r is not None:
        if r.get("cross_scope") is not False:
            fail(f"triage-single: ordinary single-feature body must be "
                 f"cross_scope false; got {r.get('cross_scope')!r}")
        elif "cross_scope" not in r:
            fail("triage-single: cross_scope key must always be present")
        else:
            ok("triage: ordinary single-feature body -> cross_scope false")


# (4) cross_scope key present on a NON-work decision too (malformed labels).
with tempfile.TemporaryDirectory() as repo_root:
    issue_payload = json.dumps({
        "number": 4335, "title": "no labels",
        "body": "repo-wide change with no feature label",
        "labels": [{"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, issue_payload)
    r = triage_record("triage-nonwork", repo_root, 4335, shim_dir)
    if r is not None:
        if "cross_scope" not in r or "cross_scope_features" not in r:
            fail(f"triage-nonwork: cross_scope + cross_scope_features keys must "
                 f"be present on every decision; record keys={sorted(r)!r}")
        elif r.get("decision") != "defer":
            fail(f"triage-nonwork: expected defer (malformed labels); "
                 f"got {r.get('decision')!r}")
        else:
            ok("triage: cross_scope keys present on a non-work (defer) record")


# ===========================================================================
# PLAN-BATCH — cross_scope routing
# ===========================================================================

# (5) A cross_scope item with feature count 1 (its misleading single label)
#     must NOT be parallel-per-feature -> multi-subagent-barrier.
out = plan_json("plan-csc-singlecount", [
    {"issue": 501, "feature": "Fa", "features": ["Fa"],
     "cross_scope": True, "contract_touch": False, "priority": "high",
     "decision": "work"},
])
if out is not None:
    shape = out.get("dispatch_shapes", {}).get("501")
    if shape == "parallel-per-feature":
        fail("plan-csc-singlecount: cross_scope item must NOT be "
             "parallel-per-feature even with feature count 1")
    elif shape != "multi-subagent-barrier":
        fail(f"plan-csc-singlecount: cross_scope/count-1 item should be "
             f"multi-subagent-barrier; got {shape!r}")
    else:
        ok("plan: cross_scope count-1 item -> multi-subagent-barrier (never "
           "parallel-per-feature)")


# (6) A cross_scope item with many features (>= threshold) -> decomposition.
out = plan_json("plan-csc-decompose", [
    {"issue": 502, "feature": "Fa",
     "features": [f"F{i}" for i in range(10)],
     "cross_scope": True, "contract_touch": False, "priority": "high",
     "decision": "work"},
])
if out is not None:
    if out.get("dispatch_shapes", {}).get("502") != "decomposition":
        fail("plan-csc-decompose: cross_scope item at/above threshold should "
             "be decomposition")
    else:
        ok("plan: cross_scope item >= threshold -> decomposition")


# (7) cross_scope items are surfaced under cross_scope_items (sorted).
out = plan_json("plan-csc-surface", [
    {"issue": 601, "feature": "Fa", "features": ["Fa"],
     "cross_scope": True, "contract_touch": False, "priority": "high",
     "decision": "work"},
    {"issue": 602, "feature": "Fb", "features": ["Fb"],
     "cross_scope": False, "contract_touch": False, "priority": "low",
     "decision": "work"},
    {"issue": 603, "feature": "Fc", "features": ["Fc", "Fd"],
     "cross_scope": True, "contract_touch": False, "priority": "medium",
     "decision": "work"},
])
if out is not None:
    if "cross_scope_items" not in out:
        fail("plan-csc-surface: cross_scope_items key must always be present")
    elif out.get("cross_scope_items") != [601, 603]:
        fail(f"plan-csc-surface: cross_scope_items should be [601, 603] sorted; "
             f"got {out.get('cross_scope_items')!r}")
    else:
        ok("plan: cross_scope_items lists the cross_scope work items, sorted")


# (8) No cross_scope items -> cross_scope_items is present and empty.
out = plan_json("plan-csc-empty", [
    {"issue": 701, "feature": "Fa", "features": ["Fa"],
     "cross_scope": False, "contract_touch": False, "priority": "high",
     "decision": "work"},
])
if out is not None:
    if out.get("cross_scope_items") != []:
        fail(f"plan-csc-empty: cross_scope_items should be [] when none; "
             f"got {out.get('cross_scope_items')!r}")
    elif out.get("dispatch_shapes", {}).get("701") != "parallel-per-feature":
        fail("plan-csc-empty: a non-cross_scope single-feature item must STILL "
             "be parallel-per-feature (no regression)")
    else:
        ok("plan: no cross_scope items -> empty cross_scope_items; ordinary "
           "single-feature shaping unaffected")


# (9) A cross_scope RESEARCH item is unaffected (still 'research', not in
#     cross_scope_items since it's findings, not code-producing work).
out = plan_json("plan-csc-research", [
    {"issue": 801, "feature": "Fa", "features": ["Fa"],
     "cross_scope": True, "contract_touch": False, "priority": "high",
     "decision": "research"},
])
if out is not None:
    if out.get("dispatch_shapes", {}).get("801") != "research":
        fail("plan-csc-research: a research item must still be shaped 'research'")
    elif out.get("cross_scope_items") != []:
        fail(f"plan-csc-research: a research item must NOT appear in "
             f"cross_scope_items; got {out.get('cross_scope_items')!r}")
    else:
        ok("plan: cross_scope research item stays 'research', not in "
           "cross_scope_items")


sys.exit(FAIL)
