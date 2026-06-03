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
        "labels": [{"name": "rabbit-managed"}],  # no feature: or priority:
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
        # blocked-by: declared but with no integer reference — ambiguous.
        "body": "Has blocked-by: somewhere but no number\n",
        "labels": [
            {"name": "rabbit-managed"},
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
        "body": "Has blocked-by: somewhere but no number\n",
        "labels": [
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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
            {"name": "rabbit-managed"},
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


sys.exit(FAIL)
