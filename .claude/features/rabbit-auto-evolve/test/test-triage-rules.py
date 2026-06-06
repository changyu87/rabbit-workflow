#!/usr/bin/env python3
"""test-triage-rules.py — e2e tests for scripts/triage-issue.py (Inv 3).

Covers the seven-rule decision table plus the needs-judgment ambiguity
default and a --help smoke test.

The script is invoked as a subprocess; a `gh` shim is placed on $PATH so
no real network call occurs. Each test constructs a tempdir-scoped fake
repo with the feature(s) the issue references, plus the gh shim that
serves the right fixture JSON for the requested gh subcommand.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "triage-issue.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# ---------------------------------------------------------------------------
# Helpers — build a fake repo + gh shim under a tempdir.
# ---------------------------------------------------------------------------
def write_shim(shim_dir, view_responses, list_response):
    """Write a `gh` shim that dispatches by subcommand.

    view_responses: dict mapping issue-number-string -> JSON string to emit
                    for `gh issue view <N> ...`.
    list_response:  JSON string emitted for `gh issue list ...`.
    """
    shim_path = os.path.join(shim_dir, "gh")
    # Write each view response and the list response into separate files
    # the shim can `cat`. This avoids brittle multi-line escaping inside
    # the shell script.
    for num, payload in view_responses.items():
        with open(os.path.join(shim_dir, f"view-{num}.json"), "w") as f:
            f.write(payload)
    with open(os.path.join(shim_dir, "list.json"), "w") as f:
        f.write(list_response)

    with open(shim_path, "w") as f:
        f.write("#!/bin/sh\n")
        f.write('# args: issue view <N> ... or issue list ...\n')
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


def make_feature(repo_root, feature_name, status="active", spec_body=""):
    """Create a minimal feature dir with feature.json + spec.md."""
    fdir = os.path.join(repo_root, ".claude", "features", feature_name)
    os.makedirs(os.path.join(fdir, "docs", "spec"), exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({
            "name": feature_name,
            "version": "0.1.0",
            "owner": "rabbit-workflow team",
            "status": status,
            "deprecation_criterion": "n/a",
        }, f)
    with open(os.path.join(fdir, "docs", "spec", "spec.md"), "w") as f:
        f.write("---\n")
        f.write(f"feature: {feature_name}\n")
        f.write("version: 0.1.0\n")
        f.write("owner: rabbit-workflow team\n")
        f.write("---\n\n")
        f.write("# Spec\n\n")
        f.write(spec_body or "Body of the spec.\n")


def run_script(repo_root, issue_num, shim_dir):
    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_ISSUE_REPO"] = "testowner/testrepo"
    # Run with cwd = repo_root so the script's relative
    # `.claude/features/<X>/` lookups land on our tempdir fake.
    return subprocess.run(
        [sys.executable, SCRIPT, str(issue_num)],
        capture_output=True, text=True, env=env, cwd=repo_root,
    )


def expect_decision(label, proc, want_decision, want_reason,
                    extra_assert=None):
    if proc.returncode != 0:
        fail(f"{label}: expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
        return
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"{label}: stdout not JSON ({e}); got {proc.stdout!r}")
        return
    if result.get("decision") != want_decision:
        fail(f"{label}: decision={result.get('decision')!r}, want {want_decision!r}; result={result!r}")
        return
    if result.get("reason_code") != want_reason:
        fail(f"{label}: reason_code={result.get('reason_code')!r}, want {want_reason!r}; result={result!r}")
        return
    if extra_assert is not None:
        msg = extra_assert(result)
        if msg:
            fail(f"{label}: {msg}; result={result!r}")
            return
    ok(f"{label}: decision={want_decision} reason={want_reason}")


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
# Rule 1: malformed-labels (missing feature: OR priority: label)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    issue_payload = json.dumps({
        "number": 101,
        "title": "Do thing X",
        "body": "Some description.",
        "labels": [],  # no feature: or priority:
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"101": issue_payload}, list_payload)
    proc = run_script(repo_root, 101, shim_dir)
    expect_decision("rule1", proc, "defer", "malformed-labels")


# ---------------------------------------------------------------------------
# Rule 2: unknown-feature (feature dir does not exist)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    # No feature created — feature dir absent.
    issue_payload = json.dumps({
        "number": 102,
        "title": "Add a missing feature behavior",
        "body": "irrelevant",
        "labels": [
            {"name": "feature:nonexistent-feature"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"102": issue_payload}, list_payload)
    proc = run_script(repo_root, 102, shim_dir)
    expect_decision("rule2", proc, "close-not-planned", "unknown-feature",
                    extra_assert=lambda r: None if r.get("feature") == "nonexistent-feature" else "feature field should echo back the label value")


# ---------------------------------------------------------------------------
# Rule 3: duplicate (title is case-folded substring of recently-closed)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "my-feature")
    issue_payload = json.dumps({
        "number": 103,
        "title": "fix login bug",
        "body": "Login is broken.",
        "labels": [
            {"name": "feature:my-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    # Closed issue title contains our (case-folded) new issue title as
    # a substring.
    list_payload = json.dumps([
        {"number": 90, "title": "Please FIX LOGIN BUG immediately", "state": "CLOSED"},
    ])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"103": issue_payload}, list_payload)
    proc = run_script(repo_root, 103, shim_dir)
    expect_decision("rule3", proc, "close-not-planned", "duplicate")


# ---------------------------------------------------------------------------
# Rule 4: feature-retired
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "old-feature", status="retired")
    issue_payload = json.dumps({
        "number": 104,
        "title": "Improve old feature",
        "body": "Body",
        "labels": [
            {"name": "feature:old-feature"},
            {"name": "priority:low"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"104": issue_payload}, list_payload)
    proc = run_script(repo_root, 104, shim_dir)
    expect_decision("rule4", proc, "close-not-planned", "feature-retired")


# ---------------------------------------------------------------------------
# Rule 5: blocked (blocked-by: #N where #N is still open)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "blocked-feature")
    issue_payload_main = json.dumps({
        "number": 105,
        "title": "Add the thing",
        "body": "We can't do this yet. blocked-by: #200",
        "labels": [
            {"name": "feature:blocked-feature"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    issue_payload_dep = json.dumps({
        "number": 200,
        "state": "OPEN",
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"105": issue_payload_main, "200": issue_payload_dep}, list_payload)
    proc = run_script(repo_root, 105, shim_dir)
    expect_decision("rule5", proc, "defer", "blocked",
                    extra_assert=lambda r: None if r.get("blocked_by") == [200] else f"blocked_by should be [200], got {r.get('blocked_by')!r}")


# ---------------------------------------------------------------------------
# Rule 6: already-spec'd (title substring already present in spec head matter)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(
        repo_root,
        "specd-feature",
        spec_body="The script supports unique-marker-phrase support as documented.\n",
    )
    issue_payload = json.dumps({
        "number": 106,
        "title": "Please add unique-marker-phrase support",
        "body": "Body",
        "labels": [
            {"name": "feature:specd-feature"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"106": issue_payload}, list_payload)
    proc = run_script(repo_root, 106, shim_dir)
    expect_decision("rule6", proc, "close-not-planned", "already-spec'd")


# ---------------------------------------------------------------------------
# Rule 7: actionable / work (default — none of rules 1-6 match)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "active-feature")
    issue_payload = json.dumps({
        "number": 107,
        "title": "Add brand-new-behavior to active-feature",
        "body": "Implement this fresh behavior.",
        "labels": [
            {"name": "feature:active-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"107": issue_payload}, list_payload)
    proc = run_script(repo_root, 107, shim_dir)
    expect_decision("rule7", proc, "work", "actionable",
                    extra_assert=lambda r: None if r.get("feature") == "active-feature" else f"feature should be 'active-feature', got {r.get('feature')!r}")


# ---------------------------------------------------------------------------
# Ambiguity: malformed blocked-by syntax → defer/needs-judgment
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "amb-feature")
    issue_payload = json.dumps({
        "number": 108,
        "title": "Some new behavior",
        # Structural leading blocked-by: line with no integer reference —
        # malformed declaration → ambiguous (issue #941: must be a STRUCTURAL
        # declaration, not a prose mention, to trigger needs-judgment).
        "body": "Intro.\n\nblocked-by: somewhere but no number\n",
        "labels": [
            {"name": "feature:amb-feature"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"108": issue_payload}, list_payload)
    proc = run_script(repo_root, 108, shim_dir)
    expect_decision("ambiguity", proc, "defer", "needs-judgment")


# ---------------------------------------------------------------------------
# Part A (issue #423): every defer decision carries a non-empty planning_note
# describing what analysis would unblock dispatch. Exercised here via the
# needs-judgment ambiguity path (a valid issue that cannot be confidently
# scoped now — e.g. malformed blocked-by syntax).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "note-feature")
    issue_payload = json.dumps({
        "number": 120,
        "title": "Some valid but unscoped behavior",
        # Structural leading blocked-by: line, no integer ref → defer note.
        "body": "Intro.\n\nblocked-by: somewhere but no number\n",
        "labels": [
            {"name": "feature:note-feature"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"120": issue_payload}, list_payload)
    proc = run_script(repo_root, 120, shim_dir)
    expect_decision(
        "defer-planning-note", proc, "defer", "needs-judgment",
        extra_assert=lambda r: (
            None
            if isinstance(r.get("planning_note"), str) and r["planning_note"].strip()
            else "defer decision must carry a non-empty string planning_note"
        ),
    )


# ---------------------------------------------------------------------------
# Part A (issue #423): the classifier MUST NOT ever emit `close-completed`.
# Every decision across the rule table is in the allowed set
# {work, defer, close-not-planned}. Assert a work scenario yields an allowed
# decision (never close-completed) and that work decisions carry a null
# planning_note (planning_note is meaningful only for defer).
# ---------------------------------------------------------------------------
_ALLOWED_DECISIONS = {"work", "defer", "close-not-planned"}
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "sweep-feature")
    issue_payload = json.dumps({
        "number": 121,
        "title": "Add a brand-new sweep behavior",
        "body": "Implement this fresh behavior.",
        "labels": [
            {"name": "feature:sweep-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"121": issue_payload}, list_payload)
    proc = run_script(repo_root, 121, shim_dir)
    if proc.returncode != 0:
        fail(f"no-close-completed: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            result = json.loads(proc.stdout)
            decision = result.get("decision")
            if decision == "close-completed":
                fail("no-close-completed: classifier emitted close-completed")
            elif decision not in _ALLOWED_DECISIONS:
                fail(f"no-close-completed: decision {decision!r} not in "
                     f"{_ALLOWED_DECISIONS}")
            elif decision == "work" and result.get("planning_note") is not None:
                fail(f"no-close-completed: work decision should have null "
                     f"planning_note, got {result.get('planning_note')!r}")
            else:
                ok("no-close-completed: work decision, allowed set, null note")
        except json.JSONDecodeError as e:
            fail(f"no-close-completed: bad JSON {e}")


# ---------------------------------------------------------------------------
# contract_touch: feature:contract label → true
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "contract")
    issue_payload = json.dumps({
        "number": 109,
        "title": "Touch the contract",
        "body": "Body",
        "labels": [
            {"name": "feature:contract"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"109": issue_payload}, list_payload)
    proc = run_script(repo_root, 109, shim_dir)

    if proc.returncode != 0:
        fail(f"contract_touch: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        try:
            result = json.loads(proc.stdout)
            if not result.get("contract_touch"):
                fail(f"contract_touch: expected true, got {result!r}")
            else:
                ok("contract_touch: true on feature:contract label")
        except json.JSONDecodeError as e:
            fail(f"contract_touch: bad JSON {e}")


# ---------------------------------------------------------------------------
# Comment-thread reconciliation (issue #463): a correction comment that
# uses supersession language supersedes the original body. Triage must read
# the full thread and reflect the corrected intent — decision=work with the
# rationale noting that a correction was applied.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "corr-feature")
    issue_payload = json.dumps({
        "number": 463,
        "title": "Migrate layout",
        "body": "Rename docs/spec/ to specs/.",
        "labels": [
            {"name": "feature:corr-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [
            {"author": {"login": "maint"}, "createdAt": "2026-06-01T00:00:00Z",
             "body": "Correction: the specs/ framing was lazy. The corrected "
                     "proposal is docs/{spec,contract,CHANGELOG}.md. This "
                     "supersedes the original body."},
        ],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"463": issue_payload}, list_payload)
    proc = run_script(repo_root, 463, shim_dir)
    expect_decision(
        "recon-correction", proc, "work", "actionable",
        extra_assert=lambda r: (
            None
            if "correction" in (r.get("rationale") or "").lower()
            else "rationale must note that a correction was applied"
        ),
    )


# ---------------------------------------------------------------------------
# Comment-thread reconciliation (issue #463): a REOPENED issue whose retitle
# conflicts with the body on the target, with no single coherent latest
# intent → defer/needs-judgment with a planning_note naming both targets.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "reopen-feature")
    issue_payload = json.dumps({
        "number": 464,
        # Title points at docs/; body points at specs/ — conflicting targets.
        "title": "Migrate layout -> docs/{spec,contract,CHANGELOG}.md",
        "body": "Rename docs/spec/ to specs/ across the repo.",
        "labels": [
            {"name": "feature:reopen-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": "reopened",
        "comments": [
            {"author": {"login": "maint"}, "createdAt": "2026-06-01T00:00:00Z",
             "body": "Reopening — I'm not sure which target is right anymore."},
        ],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"464": issue_payload}, list_payload)
    proc = run_script(repo_root, 464, shim_dir)
    expect_decision(
        "recon-reopen-conflict", proc, "defer", "needs-judgment",
        extra_assert=lambda r: (
            None
            if isinstance(r.get("planning_note"), str)
            and "docs/" in r["planning_note"]
            and "specs/" in r["planning_note"]
            else "planning_note must name both conflicting targets"
        ),
    )


# ---------------------------------------------------------------------------
# Comment-thread reconciliation (issue #463): NO-REGRESSION guard. An
# actionable issue with no comments and no title/body conflict must reconcile
# to the exact pre-#463 behavior — decision=work, reason_code=actionable,
# and NO correction noted in the rationale.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "noregress-feature")
    issue_payload = json.dumps({
        "number": 465,
        "title": "Add brand-new-behavior to noregress-feature",
        "body": "Implement this fresh behavior.",
        "labels": [
            {"name": "feature:noregress-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"465": issue_payload}, list_payload)
    proc = run_script(repo_root, 465, shim_dir)
    expect_decision(
        "recon-no-regression", proc, "work", "actionable",
        extra_assert=lambda r: (
            None
            if "correction" not in (r.get("rationale") or "").lower()
            else "no-comment/no-conflict issue must not note a correction"
        ),
    )


# ---------------------------------------------------------------------------
# Research classification (issue #478): a "study X" issue asking for findings,
# with no concrete code-change target, must classify as decision=research
# (reason_code=research) with a non-empty planning_note — and NEVER
# close-not-planned. The research path is the loop's 4th dispatch shape.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "research-feature")
    issue_payload = json.dumps({
        "number": 478,
        "title": "Study the tradeoffs of caching strategies",
        "body": ("We should investigate the available caching approaches and "
                 "recommend which one fits best. Please produce findings and a "
                 "recommendation — no code change is expected, just an "
                 "analysis report."),
        "labels": [
            {"name": "feature:research-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"478": issue_payload}, list_payload)
    proc = run_script(repo_root, 478, shim_dir)
    expect_decision(
        "research-study", proc, "research", "research",
        extra_assert=lambda r: (
            None
            if (isinstance(r.get("planning_note"), str)
                and r["planning_note"].strip())
            else "research decision must carry a non-empty planning_note"
        ),
    )
    # Defense-in-depth: a research item must NEVER be close-not-planned.
    try:
        _res = json.loads(proc.stdout)
        if _res.get("decision") == "close-not-planned":
            fail("research-study: research item must NEVER be close-not-planned")
        else:
            ok("research-study: research item not closed not-planned")
    except json.JSONDecodeError:
        pass


# ---------------------------------------------------------------------------
# Research over-trigger guard (issue #478): a normal "implement X" actionable
# issue with NO research verb must stay decision=work — the research path must
# not capture ordinary code-change items.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "impl-feature")
    issue_payload = json.dumps({
        "number": 479,
        "title": "Add a retry wrapper to the fetch helper",
        "body": ("Implement a retry wrapper around the fetch helper so "
                 "transient failures are retried up to 3 times."),
        "labels": [
            {"name": "feature:impl-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"479": issue_payload}, list_payload)
    proc = run_script(repo_root, 479, shim_dir)
    expect_decision("research-no-overtrigger", proc, "work", "actionable")


# ---------------------------------------------------------------------------
# Priority field (issue #484): the triage record MUST carry a `priority` key
# echoing the issue's `priority:<level>` label value. plan-batch.py consumes
# `priority` as its PRIMARY ordering key; without it the priority-primary
# ordering (#479) silently collapses to the contract-touch-only tiebreak.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "prio-feature")
    issue_payload = json.dumps({
        "number": 484,
        "title": "Add a brand-new prio behavior",
        "body": "Implement this fresh behavior.",
        "labels": [
            {"name": "feature:prio-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"484": issue_payload}, list_payload)
    proc = run_script(repo_root, 484, shim_dir)
    expect_decision(
        "priority-high", proc, "work", "actionable",
        extra_assert=lambda r: (
            None if r.get("priority") == "high"
            else f"priority should be 'high', got {r.get('priority')!r}"
        ),
    )


# ---------------------------------------------------------------------------
# Priority field — null case (issue #484): a malformed-labels issue with no
# `priority:` label must still carry a `priority` KEY set to null (the field
# is always present so plan-batch can rely on it; absent priority sorts last).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    issue_payload = json.dumps({
        "number": 485,
        "title": "Do thing with no priority label",
        "body": "Some description.",
        "labels": [],  # no priority: label
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"485": issue_payload}, list_payload)
    proc = run_script(repo_root, 485, shim_dir)
    expect_decision(
        "priority-null", proc, "defer", "malformed-labels",
        extra_assert=lambda r: (
            None if ("priority" in r and r.get("priority") is None)
            else "priority key must be present and null when no "
                 f"priority: label; got {r.get('priority')!r} "
                 f"(present={'priority' in r})"
        ),
    )


# ---------------------------------------------------------------------------
# Stage-2 cross-feature detection by BARE feature name (issue #443).
#
# An issue whose body names multiple features by bare name (no full
# `.claude/features/<name>/` path) — e.g. in prose or a markdown table —
# must still populate `features` with every named feature so plan-batch
# chooses a cross-feature dispatch shape. Before #443 such issues were seen
# as single-feature and got `parallel-per-feature` instead of
# `multi-subagent-barrier` / `decomposition`.
# ---------------------------------------------------------------------------

# Case A: three features named by bare name in prose (no full paths). The
# fake repo contains all three feature dirs so `ls .claude/features/`
# discovers them. `features` must include exactly those 3.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    make_feature(repo_root, "rabbit-issue")
    make_feature(repo_root, "rabbit-meta")
    issue_payload = json.dumps({
        "number": 443,
        "title": "Cross-feature refactor",
        "body": "#416 touches rabbit-auto-evolve, rabbit-issue, rabbit-meta "
                "in one pass.",
        "labels": [
            {"name": "feature:rabbit-auto-evolve"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"443": issue_payload}, list_payload)
    proc = run_script(repo_root, 443, shim_dir)
    expect_decision(
        "bare-name-prose", proc, "work", "actionable",
        extra_assert=lambda r: (
            None if r.get("features") == [
                "rabbit-auto-evolve", "rabbit-issue", "rabbit-meta"]
            else "features should be the 3 bare-named features (sorted); "
                 f"got {r.get('features')!r}"
        ),
    )


# Case B (regression fixture from acceptance): a markdown table naming three
# features by bare name, no full paths → len(features) == 3.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    make_feature(repo_root, "rabbit-issue")
    make_feature(repo_root, "rabbit-meta")
    table_body = (
        "Affected features:\n\n"
        "| feature | reason |\n"
        "| --- | --- |\n"
        "| rabbit-auto-evolve | triage logic |\n"
        "| rabbit-issue | label flow |\n"
        "| rabbit-meta | registry |\n"
    )
    issue_payload = json.dumps({
        "number": 4430,
        "title": "Table-driven cross-feature change",
        "body": table_body,
        "labels": [
            {"name": "feature:rabbit-auto-evolve"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"4430": issue_payload}, list_payload)
    proc = run_script(repo_root, 4430, shim_dir)
    expect_decision(
        "bare-name-table", proc, "work", "actionable",
        extra_assert=lambda r: (
            None if len(r.get("features") or []) == 3
            else "features should have len 3 from the markdown table; "
                 f"got {r.get('features')!r}"
        ),
    )


# Case C: bare feature name in the TITLE (not body) is also detected.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    make_feature(repo_root, "rabbit-config")
    issue_payload = json.dumps({
        "number": 4431,
        "title": "Wire rabbit-config into the evolve loop",
        "body": "Self-explanatory.",
        "labels": [
            {"name": "feature:rabbit-auto-evolve"},
            {"name": "priority:low"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"4431": issue_payload}, list_payload)
    proc = run_script(repo_root, 4431, shim_dir)
    expect_decision(
        "bare-name-title", proc, "work", "actionable",
        extra_assert=lambda r: (
            None if r.get("features") == [
                "rabbit-auto-evolve", "rabbit-config"]
            else "title-named feature must be detected; "
                 f"got {r.get('features')!r}"
        ),
    )


# Case D: a feature name appearing only as a SUBSTRING of a longer token must
# NOT match (word-boundary discipline). The repo has a feature `rabbit-meta`;
# a body that only mentions `rabbit-metadata-store` (an unrelated longer word,
# not a real feature dir) must not pull `rabbit-meta` into the set.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "rabbit-auto-evolve")
    make_feature(repo_root, "rabbit-meta")
    issue_payload = json.dumps({
        "number": 4432,
        "title": "Single-feature tweak",
        "body": "This only mentions rabbit-metadata-store, nothing else.",
        "labels": [
            {"name": "feature:rabbit-auto-evolve"},
            {"name": "priority:low"},
        ],
        "state": "OPEN",
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"4432": issue_payload}, list_payload)
    proc = run_script(repo_root, 4432, shim_dir)
    expect_decision(
        "bare-name-no-substring", proc, "work", "actionable",
        extra_assert=lambda r: (
            None if r.get("features") == ["rabbit-auto-evolve"]
            else "substring of a longer token must NOT match a feature name; "
                 f"got {r.get('features')!r}"
        ),
    )


# ---------------------------------------------------------------------------
# issue_type + created_at fields (issue #606 / Inv 44): the triage record MUST
# carry `issue_type` (derived from the GH bug/enhancement label) and
# `created_at` (the issue's creation timestamp) so plan-batch's _computed_score
# bug and age signals are non-zero. Without these fields both signals silently
# contribute 0 (the #606 dead-letter symptom).
# ---------------------------------------------------------------------------

# Case: a BUG-labelled issue → issue_type == "bug", created_at echoed through.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "bug-feature")
    issue_payload = json.dumps({
        "number": 606,
        "title": "Fix the broken thing in bug-feature",
        "body": "Implement this fix.",
        "labels": [
            {"name": "feature:bug-feature"},
            {"name": "priority:high"},
            {"name": "bug"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
        "createdAt": "2026-01-02T03:04:05Z",
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"606": issue_payload}, list_payload)
    proc = run_script(repo_root, 606, shim_dir)
    expect_decision(
        "type-bug", proc, "work", "actionable",
        extra_assert=lambda r: (
            None
            if r.get("issue_type") == "bug"
            and r.get("created_at") == "2026-01-02T03:04:05Z"
            else "bug issue must emit issue_type 'bug' and the createdAt "
                 f"timestamp; got issue_type={r.get('issue_type')!r}, "
                 f"created_at={r.get('created_at')!r}"
        ),
    )


# Case: an ENHANCEMENT-labelled issue → issue_type == "enhancement".
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "enh-feature")
    issue_payload = json.dumps({
        "number": 6061,
        "title": "Add a brand-new behavior to enh-feature",
        "body": "Implement this fresh behavior.",
        "labels": [
            {"name": "feature:enh-feature"},
            {"name": "priority:medium"},
            {"name": "enhancement"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
        "createdAt": "2026-05-30T00:00:00Z",
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"6061": issue_payload}, list_payload)
    proc = run_script(repo_root, 6061, shim_dir)
    expect_decision(
        "type-enhancement", proc, "work", "actionable",
        extra_assert=lambda r: (
            None
            if r.get("issue_type") == "enhancement"
            and r.get("created_at") == "2026-05-30T00:00:00Z"
            else "enhancement issue must emit issue_type 'enhancement'; "
                 f"got issue_type={r.get('issue_type')!r}, "
                 f"created_at={r.get('created_at')!r}"
        ),
    )


# Case: BOTH bug and enhancement labels → bug wins (higher-urgency signal).
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "both-feature")
    issue_payload = json.dumps({
        "number": 6062,
        "title": "Add a behavior to both-feature",
        "body": "Implement this.",
        "labels": [
            {"name": "feature:both-feature"},
            {"name": "priority:high"},
            {"name": "enhancement"},
            {"name": "bug"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
        "createdAt": "2026-04-01T00:00:00Z",
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"6062": issue_payload}, list_payload)
    proc = run_script(repo_root, 6062, shim_dir)
    expect_decision(
        "type-both-bug-wins", proc, "work", "actionable",
        extra_assert=lambda r: (
            None if r.get("issue_type") == "bug"
            else "both bug+enhancement labels must resolve to 'bug'; "
                 f"got {r.get('issue_type')!r}"
        ),
    )


# Case: NO type label → issue_type is null but the KEY is always present;
# created_at is null when gh returns no createdAt.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "notype-feature")
    issue_payload = json.dumps({
        "number": 6063,
        "title": "Add a behavior to notype-feature",
        "body": "Implement this.",
        "labels": [
            {"name": "feature:notype-feature"},
            {"name": "priority:low"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
        # No createdAt key at all.
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"6063": issue_payload}, list_payload)
    proc = run_script(repo_root, 6063, shim_dir)
    expect_decision(
        "type-none-null-keys", proc, "work", "actionable",
        extra_assert=lambda r: (
            None
            if ("issue_type" in r and r.get("issue_type") is None
                and "created_at" in r and r.get("created_at") is None)
            else "no-type/no-createdAt issue must carry issue_type:null AND "
                 f"created_at:null (keys present); got "
                 f"issue_type={r.get('issue_type')!r} "
                 f"(present={'issue_type' in r}), "
                 f"created_at={r.get('created_at')!r} "
                 f"(present={'created_at' in r})"
        ),
    )


# ---------------------------------------------------------------------------
# Rule 5 over-match regression (issue #941): a body that merely MENTIONS the
# `blocked-by:` token in PROSE (describing/discussing the dependency mechanism
# — in a sentence, code span, or table) does NOT declare a real ordering
# dependency and MUST pass through as actionable `work`, NEVER deferred. Before
# the fix the substring `_BLOCKED_BY_ANY` match false-deferred such issues
# `defer`/`needs-judgment`. Body modelled on issues that propose to redesign
# the mechanism itself.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "prose-feature")
    prose_body = (
        "The triage parser over-matches: it treats any literal `blocked-by:` "
        "substring as a dependency. We should only honor the real "
        "`blocked-by: #N` form, or a line that starts with the blocked-by "
        "token. This issue DESCRIBES the mechanism; it declares no actual "
        "blocker. See the `blocked-by:NNN` labels and the body regex.\n"
    )
    issue_payload = json.dumps({
        "number": 941,
        "title": "Redesign the blocked-by detection in triage",
        "body": prose_body,
        "labels": [
            {"name": "feature:prose-feature"},
            {"name": "priority:high"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"941": issue_payload}, list_payload)
    proc = run_script(repo_root, 941, shim_dir)
    expect_decision("blocked-by-prose-passthrough", proc, "work", "actionable")


# Rule 5 (issue #941): a GENUINE `blocked-by: #N` declaration still parses N
# and (when the cited dep is open) defers `blocked` with blocked_by == [N].
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "realdep-feature")
    issue_payload_main = json.dumps({
        "number": 9410,
        "title": "Do the thing once unblocked",
        "body": "Cannot start yet.\n\nblocked-by: #123\n",
        "labels": [
            {"name": "feature:realdep-feature"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    issue_payload_dep = json.dumps({"number": 123, "state": "OPEN"})
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir,
               {"9410": issue_payload_main, "123": issue_payload_dep},
               list_payload)
    proc = run_script(repo_root, 9410, shim_dir)
    expect_decision(
        "blocked-by-real-dep-extracts-N", proc, "defer", "blocked",
        extra_assert=lambda r: (
            None if r.get("blocked_by") == [123]
            else f"blocked_by should be [123], got {r.get('blocked_by')!r}"
        ),
    )


# Rule 5 (issue #941): a STRUCTURAL leading `blocked-by:` line with no valid
# `#N` is the sole malformed case → defer/needs-judgment (conservative).
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "malformed-feature")
    issue_payload = json.dumps({
        "number": 9411,
        "title": "Some behavior with a botched dependency line",
        "body": "Intro.\n\nblocked-by: TBD\n",
        "labels": [
            {"name": "feature:malformed-feature"},
            {"name": "priority:medium"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir, {"9411": issue_payload}, list_payload)
    proc = run_script(repo_root, 9411, shim_dir)
    expect_decision("blocked-by-structural-malformed", proc,
                    "defer", "needs-judgment")


# Rule 5 (issue #941): a structural leading `blocked-by:` line that carries
# list/quote markers and a valid `#N` (open dep) still defers `blocked`.
with tempfile.TemporaryDirectory() as repo_root:
    make_feature(repo_root, "listdep-feature")
    issue_payload_main = json.dumps({
        "number": 9412,
        "title": "Bullet-listed dependency",
        "body": "Deps:\n\n- blocked-by: #456\n",
        "labels": [
            {"name": "feature:listdep-feature"},
            {"name": "priority:low"},
        ],
        "state": "OPEN",
        "stateReason": None,
        "comments": [],
    })
    issue_payload_dep = json.dumps({"number": 456, "state": "OPEN"})
    list_payload = json.dumps([])
    shim_dir = os.path.join(repo_root, "shim")
    os.makedirs(shim_dir)
    write_shim(shim_dir,
               {"9412": issue_payload_main, "456": issue_payload_dep},
               list_payload)
    proc = run_script(repo_root, 9412, shim_dir)
    expect_decision(
        "blocked-by-list-marker-dep", proc, "defer", "blocked",
        extra_assert=lambda r: (
            None if r.get("blocked_by") == [456]
            else f"blocked_by should be [456], got {r.get('blocked_by')!r}"
        ),
    )


sys.exit(FAIL)
