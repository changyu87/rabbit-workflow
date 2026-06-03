#!/usr/bin/env python3
"""test-dispatch-shape.py — e2e tests for the two-stage decoupling of
work-selection (Stage 1) from dispatch-shape (Stage 2) per Inv 26
(issue #435).

Two surfaces are exercised end-to-end:

  - plan-batch.py — emits `selection_order` (Stage 1, dispatch-shape blind)
    and `dispatch_shapes` (Stage 2, item-shaped) alongside the existing
    barrier_first / groups plan.
  - triage-issue.py — emits a `features` list (the distinct feature dirs an
    item touches: union of the feature:<name> label and any
    `.claude/features/<name>/` path reference in the body), which is the
    basis Stage 2 uses for cross-feature detection.

The three valid dispatch shapes (the maintainer struck shape 2 — the
session-override shape) are:
  - parallel-per-feature      (item edits exactly one feature dir)
  - multi-subagent-barrier    (item edits >1 feature dir, < threshold)
  - decomposition             (item edits >= --decompose-threshold features)

No shape ever emits a session override; the planner is a pure JSON
processor and writes no marker at all — this test asserts that property
explicitly.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.normpath(os.path.join(HERE, "..", "scripts", "plan-batch.py"))
TRIAGE = os.path.normpath(os.path.join(HERE, "..", "scripts", "triage-issue.py"))

VALID_SHAPES = {"parallel-per-feature", "decomposition", "multi-subagent-barrier"}
FORBIDDEN_SHAPES = {"sequential-with-override"}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


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
        fail(f"{label}: exit {proc.returncode}; stderr={proc.stderr!r}")
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"{label}: bad JSON ({e}); stdout={proc.stdout!r}")
        return None


# ---------------------------------------------------------------------------
# Stage 2 — single-feature item -> parallel-per-feature (shape 1).
# ---------------------------------------------------------------------------
out = plan_json("single-feature", [
    {"issue": 101, "feature": "Fa", "features": ["Fa"],
     "contract_touch": False, "priority": "low", "decision": "work"},
])
if out is not None:
    shapes = out.get("dispatch_shapes", {})
    if shapes.get("101") != "parallel-per-feature":
        fail(f"single-feature: shape for 101 = {shapes.get('101')!r}, "
             f"want 'parallel-per-feature'; shapes={shapes!r}")
    else:
        ok("single-feature item -> parallel-per-feature")


# ---------------------------------------------------------------------------
# Stage 2 — cross-feature item, independent edits -> multi-subagent-barrier
#           (shape 4). Three feature dirs, below the decompose threshold.
# ---------------------------------------------------------------------------
out = plan_json("cross-feature", [
    {"issue": 202, "feature": "Fa", "features": ["Fa", "Fb", "Fc"],
     "contract_touch": False, "priority": "medium", "decision": "work"},
])
if out is not None:
    shapes = out.get("dispatch_shapes", {})
    if shapes.get("202") != "multi-subagent-barrier":
        fail(f"cross-feature: shape for 202 = {shapes.get('202')!r}, "
             f"want 'multi-subagent-barrier'; shapes={shapes!r}")
    else:
        ok("cross-feature (independent edits) -> multi-subagent-barrier")


# ---------------------------------------------------------------------------
# Stage 2 — very large item touching 10+ features -> decomposition (shape 3).
# ---------------------------------------------------------------------------
big_features = [f"F{i}" for i in range(11)]
out = plan_json("very-large", [
    {"issue": 303, "feature": "F0", "features": big_features,
     "contract_touch": False, "priority": "high", "decision": "work"},
])
if out is not None:
    shapes = out.get("dispatch_shapes", {})
    if shapes.get("303") != "decomposition":
        fail(f"very-large: shape for 303 = {shapes.get('303')!r}, "
             f"want 'decomposition'; shapes={shapes!r}")
    else:
        ok("very-large item (11 features) -> decomposition")


# ---------------------------------------------------------------------------
# Stage 2 — exactly at threshold (default 10) -> decomposition (>= rule).
# ---------------------------------------------------------------------------
out = plan_json("at-threshold", [
    {"issue": 304, "feature": "F0", "features": [f"F{i}" for i in range(10)],
     "contract_touch": False, "priority": "high", "decision": "work"},
])
if out is not None:
    shapes = out.get("dispatch_shapes", {})
    if shapes.get("304") != "decomposition":
        fail(f"at-threshold: shape for 304 = {shapes.get('304')!r}, "
             f"want 'decomposition' (10 >= default threshold 10)")
    else:
        ok("at-threshold (10 features) -> decomposition")


# ---------------------------------------------------------------------------
# Stage 2 — --decompose-threshold override raises/lowers the cut-off; a
#           5-feature item is multi-subagent-barrier under default 10 but
#           decomposition when threshold=5.
# ---------------------------------------------------------------------------
five = {"issue": 305, "feature": "F0", "features": [f"F{i}" for i in range(5)],
        "contract_touch": False, "priority": "high", "decision": "work"}
out = plan_json("five-default", [five])
if out is not None:
    if out.get("dispatch_shapes", {}).get("305") != "multi-subagent-barrier":
        fail("five-default: 5 features under default threshold 10 should be "
             "multi-subagent-barrier")
    else:
        ok("five features (default threshold) -> multi-subagent-barrier")
out = plan_json("five-thresh5", [five], ["--decompose-threshold", "5"])
if out is not None:
    if out.get("dispatch_shapes", {}).get("305") != "decomposition":
        fail("five-thresh5: 5 features with --decompose-threshold 5 should be "
             "decomposition")
    else:
        ok("five features (--decompose-threshold 5) -> decomposition")


# ---------------------------------------------------------------------------
# Stage 2 — items missing a `features` list fall back to the single
#           `feature` label (count 1) -> parallel-per-feature. Backward-compat
#           with pre-#435 triage objects.
# ---------------------------------------------------------------------------
out = plan_json("no-features-field", [
    {"issue": 306, "feature": "Fa", "contract_touch": False,
     "priority": "low", "decision": "work"},
])
if out is not None:
    if out.get("dispatch_shapes", {}).get("306") != "parallel-per-feature":
        fail("no-features-field: missing features list should fall back to "
             "single-feature -> parallel-per-feature")
    else:
        ok("no features field -> parallel-per-feature (single-feature fallback)")


# ---------------------------------------------------------------------------
# Stage 2 — NO shape is ever the forbidden session-override shape, and the
#           planner emits ONLY the three valid shapes across a mixed batch.
# ---------------------------------------------------------------------------
mixed = [
    {"issue": 401, "feature": "Fa", "features": ["Fa"],
     "contract_touch": False, "priority": "high", "decision": "work"},
    {"issue": 402, "feature": "Fb", "features": ["Fb", "Fc"],
     "contract_touch": False, "priority": "medium", "decision": "work"},
    {"issue": 403, "feature": "Fd", "features": [f"G{i}" for i in range(12)],
     "contract_touch": False, "priority": "low", "decision": "work"},
]
out = plan_json("no-override", mixed)
if out is not None:
    shapes = out.get("dispatch_shapes", {})
    emitted = set(shapes.values())
    if emitted & FORBIDDEN_SHAPES:
        fail(f"no-override: planner emitted forbidden shape(s) "
             f"{emitted & FORBIDDEN_SHAPES}; shapes={shapes!r}")
    elif not emitted <= VALID_SHAPES:
        fail(f"no-override: planner emitted unknown shape(s) "
             f"{emitted - VALID_SHAPES}; shapes={shapes!r}")
    else:
        ok("mixed batch emits only the three valid shapes; never the "
           "struck session-override shape")
    # Defense-in-depth: the raw stdout never mentions the forbidden token.
    raw = json.dumps(out)
    if "scope-override" in raw or "sequential-with-override" in raw:
        fail("no-override: planner output references a session override")
    else:
        ok("planner output never references a session override")


# ---------------------------------------------------------------------------
# Stage 2 — non-work items get NO dispatch_shape entry (they are dropped
#           from dispatch, so a shape is meaningless for them).
# ---------------------------------------------------------------------------
out = plan_json("drop-non-work", [
    {"issue": 501, "feature": "Fa", "features": ["Fa"],
     "contract_touch": False, "priority": "high", "decision": "work"},
    {"issue": 502, "feature": "Fb", "features": ["Fb"],
     "contract_touch": False, "priority": "high", "decision": "defer"},
])
if out is not None:
    shapes = out.get("dispatch_shapes", {})
    if "502" in shapes:
        fail(f"drop-non-work: deferred 502 should have no shape; shapes={shapes!r}")
    elif shapes.get("501") != "parallel-per-feature":
        fail("drop-non-work: work item 501 should still carry its shape")
    else:
        ok("non-work items carry no dispatch_shape")


# ---------------------------------------------------------------------------
# Stage 1 — work selection is dispatch-shape BLIND.
#   A high-priority CROSS-feature item (shape 4) must be selected BEFORE a
#   low-priority SINGLE-feature item (shape 1), even though the loop's
#   performance preference is the single-feature one.
# ---------------------------------------------------------------------------
out = plan_json("stage1-blind", [
    # low-priority single-feature (shape-1 friendly) listed FIRST in input
    {"issue": 601, "feature": "Fa", "features": ["Fa"],
     "contract_touch": False, "priority": "low", "decision": "work"},
    # high-priority cross-feature (shape-4) listed SECOND in input
    {"issue": 602, "feature": "Fb", "features": ["Fb", "Fc", "Fd"],
     "contract_touch": False, "priority": "high", "decision": "work"},
])
if out is not None:
    order = out.get("selection_order")
    if not isinstance(order, list):
        fail(f"stage1-blind: selection_order missing/not a list: {order!r}")
    elif order[:2] != [602, 601]:
        fail(f"stage1-blind: high-priority cross-feature 602 must be selected "
             f"before low-priority single-feature 601; order={order!r}")
    else:
        ok("Stage 1 is dispatch-shape blind: high-priority cross-feature "
           "selected before low-priority single-feature")


# ---------------------------------------------------------------------------
# Stage 1 — selection_order is by priority desc then issue asc, and contains
#   ONLY work items (close-not-planned / defer are not selectable work).
# ---------------------------------------------------------------------------
out = plan_json("stage1-order", [
    {"issue": 703, "feature": "Fc", "features": ["Fc"],
     "contract_touch": False, "priority": "medium", "decision": "work"},
    {"issue": 701, "feature": "Fa", "features": ["Fa"],
     "contract_touch": False, "priority": "critical", "decision": "work"},
    {"issue": 702, "feature": "Fb", "features": ["Fb"],
     "contract_touch": False, "priority": "high", "decision": "work"},
    {"issue": 704, "feature": "Fd", "features": ["Fd"],
     "contract_touch": False, "priority": "high", "decision": "close-not-planned"},
])
if out is not None:
    order = out.get("selection_order")
    if order != [701, 702, 703]:
        fail(f"stage1-order: want [701,702,703] (priority desc, non-work "
             f"dropped); got {order!r}")
    else:
        ok("Stage 1 selection_order is priority-desc, work-only")


# ---------------------------------------------------------------------------
# triage-issue.py — `features` extraction (Stage-2 basis).
#   Body references two feature dirs beyond the labelled one; the emitted
#   `features` list is the sorted union.
# ---------------------------------------------------------------------------
def write_triage_shim(shim_dir, view_payload, list_payload="[]"):
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


def make_feature(repo_root, name):
    fdir = os.path.join(repo_root, ".claude", "features", name, "docs", "spec")
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(repo_root, ".claude", "features", name,
                           "feature.json"), "w") as f:
        json.dump({"name": name, "version": "0.1.0",
                   "owner": "rabbit-workflow team",
                   "status": "active", "deprecation_criterion": "n/a"}, f)
    with open(os.path.join(fdir, "spec.md"), "w") as f:
        f.write("---\nfeature: %s\nversion: 0.1.0\nowner: rabbit-workflow team\n---\n\n# Spec\n\nBody.\n" % name)


tmp = tempfile.mkdtemp()
try:
    for name in ("Fa", "Fb", "Fc"):
        make_feature(tmp, name)
    shim_dir = os.path.join(tmp, "shim")
    os.makedirs(shim_dir)
    body = ("Touches .claude/features/Fb/scripts/x.py and "
            ".claude/features/Fc/docs/spec/spec.md as well.")
    view_payload = json.dumps({
        "number": 800, "title": "cross-feature change", "body": body,
        "labels": [{"name": "feature:Fa"}, {"name": "priority:high"},
                   {"name": "rabbit-managed"}],
        "state": "OPEN", "comments": [],
    })
    write_triage_shim(shim_dir, view_payload)
    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
    proc = subprocess.run(
        [sys.executable, TRIAGE, "800"],
        capture_output=True, text=True, env=env, cwd=tmp,
    )
    if proc.returncode != 0:
        fail(f"triage-features: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            result = json.loads(proc.stdout)
            feats = result.get("features")
            if sorted(feats or []) != ["Fa", "Fb", "Fc"]:
                fail(f"triage-features: features={feats!r}, want sorted union "
                     f"['Fa','Fb','Fc']")
            else:
                ok("triage emits `features` = sorted union of label + body paths")
        except json.JSONDecodeError as e:
            fail(f"triage-features: bad JSON ({e}); stdout={proc.stdout!r}")

    # Single-feature issue (no body paths) -> features == [label].
    shim2 = os.path.join(tmp, "shim2")
    os.makedirs(shim2)
    view2 = json.dumps({
        "number": 801, "title": "single", "body": "just a normal change",
        "labels": [{"name": "feature:Fa"}, {"name": "priority:low"}],
        "state": "OPEN", "comments": [],
    })
    write_triage_shim(shim2, view2)
    env2 = os.environ.copy()
    env2["PATH"] = shim2 + os.pathsep + env2.get("PATH", "")
    env2["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
    proc = subprocess.run(
        [sys.executable, TRIAGE, "801"],
        capture_output=True, text=True, env=env2, cwd=tmp,
    )
    if proc.returncode != 0:
        fail(f"triage-features-single: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        result = json.loads(proc.stdout)
        if result.get("features") != ["Fa"]:
            fail(f"triage-features-single: features={result.get('features')!r}, "
                 f"want ['Fa']")
        else:
            ok("triage single-feature issue -> features == [label]")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


sys.exit(FAIL)
