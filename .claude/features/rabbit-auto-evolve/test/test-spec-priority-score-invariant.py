#!/usr/bin/env python3
"""test-spec-priority-score-invariant.py — rabbit-auto-evolve Inv 44
(issue #441).

Asserts the loop-computed-priority-score invariant text is present in the
feature spec (specs/spec.md, dual-read with docs/spec/ fallback per issue
#399). The invariant states:
  - the loop computes its OWN priority score from observable signals;
  - the filer-set priority: label is ONE input among several, no longer
    the sole determinant;
  - the score is the PRIMARY dispatch-ordering key, with the contract-touch
    barrier preserved as the SECONDARY tiebreak (refining issue #479) and
    issue number as the final tiebreak;
  - the score is computed deterministically in a script (not by LLM
    inference) and is emitted for transparency.
"""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
TRIAGE = str(FEATURE_DIR / "scripts" / "triage-issue.py")
PLAN = str(FEATURE_DIR / "scripts" / "plan-batch.py")
# Dual-read (issue #399): prefer the flat docs/spec.md layout, fall back to
# specs/spec.md, then legacy docs/spec/spec.md.
SPEC_MD = (FEATURE_DIR / "docs" / "spec.md")
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


text = SPEC_MD.read_text()
lowered = re.sub(r"\s+", " ", text.lower())

REQUIRED = [
    # The loop computes its own score.
    "loop computes its own priority score",
    # Filer label is one input among several.
    "filer label is one input among several",
    # Observable signals named.
    "blocking-fanout",
    # Computed score is the primary ordering key.
    "computed score is the primary",
    # The contract-touch barrier remains the secondary tiebreak (refines #479).
    "contract-touch barrier",
    # Determinism / script-tier.
    "computed in a script",
    # Transparency requirement.
    "computed_scores",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing priority-score-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the loop-computed-priority-score invariant (Inv 44)")


# ---------------------------------------------------------------------------
# E2E (issue #606 / Inv 48): the bug-vs-enhancement and age signals of the
# computed score are LIVE, non-zero contributions — they read `issue_type` and
# `created_at` that triage-issue.py now emits. Run the full pipe with no
# hand-authored signal values:
#   1. triage two issues that differ ONLY in type label + age (same priority,
#      same single-feature scope, no blocked_by):
#        #800  bug label,         old createdAt  → bug + age both fire
#        #801  enhancement label, no createdAt   → neither fires
#   2. pipe both triage records into plan-batch.py
#   3. assert computed_scores[800] > computed_scores[801] STRICTLY.
# Before #606 triage dropped issue_type/created_at, so both items scored
# identically and this assertion FAILS (RED).
# ---------------------------------------------------------------------------
def _write_shim(shim_dir, view_responses, list_response):
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


def _make_feature(repo_root, feature_name):
    fdir = os.path.join(repo_root, ".claude", "features", feature_name)
    os.makedirs(os.path.join(fdir, "specs"), exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({
            "name": feature_name, "version": "0.1.0",
            "owner": "rabbit-workflow team", "status": "active",
            "deprecation_criterion": "n/a",
        }, f)
    with open(os.path.join(fdir, "specs", "spec.md"), "w") as f:
        f.write("---\nfeature: %s\nversion: 0.1.0\n"
                "owner: rabbit-workflow team\n---\n\n# Spec\n\nBody.\n"
                % feature_name)


def _run_triage(repo_root, num, shim_dir):
    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
    return subprocess.run(
        [sys.executable, TRIAGE, str(num)],
        capture_output=True, text=True, env=env, cwd=repo_root,
    )


with tempfile.TemporaryDirectory() as repo_root:
    _make_feature(repo_root, "score-bug")
    _make_feature(repo_root, "score-enh")
    issue_bug = json.dumps({
        "number": 800,
        "title": "Add a behavior to score-bug",
        "body": "Implement this.",
        "labels": [
            {"name": "feature:score-bug"},
            {"name": "priority:medium"},
            {"name": "bug"},
        ],
        "state": "OPEN", "stateReason": None, "comments": [],
        # An old timestamp so the age signal saturates near 1.0.
        "createdAt": "2020-01-01T00:00:00Z",
    })
    issue_enh = json.dumps({
        "number": 801,
        "title": "Add a behavior to score-enh",
        "body": "Implement this.",
        "labels": [
            {"name": "feature:score-enh"},
            {"name": "priority:medium"},
            {"name": "enhancement"},
        ],
        "state": "OPEN", "stateReason": None, "comments": [],
        # No createdAt → age signal contributes 0.
    })
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    _write_shim(shim_dir, {"800": issue_bug, "801": issue_enh},
                json.dumps([]))

    records = []
    abort = False
    for num in (800, 801):
        proc = _run_triage(repo_root, num, shim_dir)
        if proc.returncode != 0:
            fail(f"score-e2e: triage #{num} exit {proc.returncode}; "
                 f"stderr={proc.stderr!r}")
            abort = True
            break
        try:
            records.append(json.loads(proc.stdout))
        except json.JSONDecodeError as e:
            fail(f"score-e2e: triage #{num} bad JSON ({e})")
            abort = True
            break

    if not abort:
        plan_proc = subprocess.run(
            [sys.executable, PLAN], input=json.dumps(records),
            capture_output=True, text=True,
        )
        if plan_proc.returncode != 0:
            fail(f"score-e2e: plan-batch exit {plan_proc.returncode}; "
                 f"stderr={plan_proc.stderr!r}")
        else:
            try:
                out = json.loads(plan_proc.stdout)
            except json.JSONDecodeError as e:
                fail(f"score-e2e: plan-batch bad JSON ({e})")
            else:
                scores = out.get("computed_scores", {})
                s_bug = scores.get("800")
                s_enh = scores.get("801")
                if s_bug is None or s_enh is None:
                    fail(f"score-e2e: computed_scores missing 800/801; "
                         f"got {scores!r}")
                elif not (s_bug > s_enh):
                    fail(f"score-e2e: bug+old item (800={s_bug}) must score "
                         f"STRICTLY HIGHER than enhancement+no-age item "
                         f"(801={s_enh}) — the bug and age signals are dead "
                         f"(triage dropped issue_type/created_at, #606)")
                else:
                    ok(f"score-e2e: bug+age signals live — 800={s_bug} > "
                       f"801={s_enh} end-to-end (Inv 48)")


sys.exit(FAIL)
