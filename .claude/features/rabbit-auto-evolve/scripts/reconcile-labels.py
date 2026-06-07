#!/usr/bin/env python3
"""reconcile-labels.py — mirror the dispatch-journal LIVE set onto the GitHub
`in-progress` category label (rabbit-auto-evolve spec.md Inv 55, issue #859).

The dispatch journal (Inv 54) is the authoritative in-flight set, but it lives
only on disk. This per-tick RECONCILE reflects the live set onto the sanctioned
`in-progress` GitHub label so the GitHub view stays truthful for any outside
observer:

  - ADD    `in-progress` to every live-set issue that is OPEN and lacks it.
  - STRIP  `in-progress` from every OPEN issue that carries it but is NOT in the
           live set (status completed/aborted, pruned from the journal, or never
           tracked) — so a crashed/interrupted tick's stale label is corrected
           on the NEXT tick (self-healing, mirroring Inv 42 / Inv 35).

It is deterministic and idempotent: the action is purely a function of the
journal-derived live set and the issues' current GitHub label state, so a
second run in a row makes NO edits.

The LIVE set is computed by REUSING status-report.py's live-set logic
(`_derive_in_flight`) so the journal-status definition is never forked.

The label is ensured to EXIST first via the rabbit-issue `ensure_labels`
mechanism (a cross-scope INVOKE of rabbit-issue/scripts/_gh.ensure_labels — NOT
a cross-feature edit), so a fresh repo missing the category label
self-bootstraps. Repo slug resolves via rabbit-issue/_gh.repo_slug (no
`git remote` shellout), matching fetch-queue.py.

`gh`/network failure is tolerated GRACEFULLY: any `gh` error is logged to stderr
and the reconcile continues, never crashing the tick (label hygiene must never
block evolution, mirroring the Inv 49 sweep's never-fail-the-tick contract).
Exit code is 0 on success including every graceful-degradation path; a non-zero
exit is reserved for a genuine invocation error.

State dir resolves via RABBIT_AUTO_EVOLVE_STATE_DIR, else `<cwd>/.rabbit`
(matching the sibling phase scripts).

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

LABEL = "in-progress"

_HERE = Path(__file__).resolve().parent

# Bridge to rabbit-issue/scripts so `from _gh import ...` works (the same
# sys.path bridge fetch-queue.py / triage-issue.py use). This is a cross-scope
# INVOKE of rabbit-issue's gh helpers, declared in docs/contract.md
# invokes.modules — rabbit-auto-evolve never edits rabbit-issue.
_RABBIT_ISSUE_SCRIPTS = _HERE.parent.parent / "rabbit-issue" / "scripts"
if str(_RABBIT_ISSUE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RABBIT_ISSUE_SCRIPTS))
from _gh import ensure_labels, repo_slug  # noqa: E402


def _load_status_report():
    """Import status-report.py (hyphenated filename) as a module so its
    live-set logic (`_derive_in_flight`) is reused, NOT re-stated. It is a
    fixed sibling of THIS file."""
    path = _HERE / "status-report.py"
    spec = importlib.util.spec_from_file_location("status_report", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _state_dir() -> str:
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _read_state() -> dict:
    path = os.path.join(_state_dir(), "auto-evolve-state.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _live_set(state: dict) -> set:
    """The LIVE in-flight issue set (Inv 54), reusing status-report.py's
    `_derive_in_flight` projection of the dispatch journal."""
    status_report = _load_status_report()
    return {n for n in status_report._derive_in_flight(state)
            if isinstance(n, int) and not isinstance(n, bool)}


def _gh_json(args: list):
    """Run `gh <args>` and return parsed JSON, or None on any failure
    (logged to stderr — never raises)."""
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    except OSError as e:
        sys.stderr.write(f"reconcile-labels: gh invocation failed: {e}\n")
        return None
    if proc.returncode != 0:
        sys.stderr.write(
            f"reconcile-labels: `gh {' '.join(args)}` failed: "
            f"{proc.stderr.strip()}\n")
        return None
    try:
        return json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        sys.stderr.write(
            f"reconcile-labels: `gh {' '.join(args)}` returned non-JSON\n")
        return None


def _labelled_open_issues(slug: str) -> set:
    """The set of OPEN issue numbers currently carrying `in-progress`."""
    data = _gh_json(["issue", "list", "-R", slug, "--state", "open",
                     "--label", LABEL, "--json", "number", "--limit", "500"])
    if not isinstance(data, list):
        return set()
    out = set()
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("number"), int):
            out.add(item["number"])
    return out


def _issue_view(slug: str, number: int):
    """The {number,state,labels} view for one issue, or None on gh failure."""
    return _gh_json(["issue", "view", str(number), "-R", slug,
                     "--json", "number,state,labels"])


def _issue_label_names(view: dict) -> set:
    return {lbl.get("name", "") for lbl in view.get("labels", [])
            if isinstance(lbl, dict)}


def _edit_label(slug: str, number: int, flag: str) -> None:
    """Apply `gh issue edit <N> <flag> in-progress`, logging any failure but
    never raising — the next issue still gets reconciled."""
    proc = subprocess.run(
        ["gh", "issue", "edit", str(number), "-R", slug, flag, LABEL],
        capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(
            f"reconcile-labels: `gh issue edit {number} {flag} {LABEL}` "
            f"failed: {proc.stderr.strip()}\n")


def reconcile() -> dict:
    """Reconcile the `in-progress` label against the journal live set.

    Returns a fixed-format summary dict. Never raises on gh/network failure."""
    slug = repo_slug()

    # Ensure the sanctioned category label exists before stamping (cross-scope
    # INVOKE of rabbit-issue). Idempotent; tolerant of duplicate/failure.
    try:
        ensure_labels([LABEL])
    except Exception as e:  # never let label bootstrap crash the tick
        sys.stderr.write(f"reconcile-labels: ensure_labels failed: {e}\n")

    live = _live_set(_read_state())
    labelled = _labelled_open_issues(slug)

    added, removed = [], []

    # ADD to live-set issues that are OPEN and missing the label.
    for number in sorted(live):
        if number in labelled:
            continue  # already labelled -> no-op (idempotent)
        view = _issue_view(slug, number)
        if view is None:
            continue  # gh failure already logged; skip gracefully
        if str(view.get("state", "")).upper() != "OPEN":
            continue  # only OPEN issues carry the live label
        if LABEL in _issue_label_names(view):
            continue  # raced/already labelled
        _edit_label(slug, number, "--add-label")
        added.append(number)

    # STRIP from labelled OPEN issues no longer in the live set.
    for number in sorted(labelled - live):
        _edit_label(slug, number, "--remove-label")
        removed.append(number)

    return {
        "status": "reconciled",
        "label": LABEL,
        "live": sorted(live),
        "added": added,
        "removed": removed,
    }


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Reconcile the GitHub `in-progress` label against the "
            "rabbit-auto-evolve dispatch-journal live set (Inv 55): add the "
            "label to newly-live open issues, strip it from open issues no "
            "longer live. Idempotent and self-healing; gh/network failure is "
            "logged and never crashes the tick. Exit 0 on success including "
            "graceful-degradation paths."
        )
    ).parse_args()

    summary = reconcile()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
