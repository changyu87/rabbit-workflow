#!/usr/bin/env python3
"""close-decomposed-parents.py — roll-up close of decomposed parents.

Usage:
  close-decomposed-parents.py

Per rabbit-auto-evolve spec.md Inv 53, a decomposition parent is de-queued and
left OPEN while its N per-feature children are worked. When all children close,
NOTHING closed the parent — it lingered OPEN indefinitely. This step closes
that gap deterministically, every tick.

It reads <state_dir>/auto-evolve-state.json and, for EVERY parent tracked in
the `decomposition_parents` map (parent-issue-number string -> child-number
list, schema 1.3.0):

  1. reads the AUTHORITATIVE close-source — the parent's GitHub-native
     sub-issue rollup, `gh api repos/{slug}/issues/<parent#>` ->
     `sub_issues_summary{total, completed}`;
  2. if the parent has sub-issues and ALL are complete
     (`total > 0 and completed == total`), closes the parent via
       gh issue close <parent#> --reason completed --comment <roll-up>
     and removes the parent key from `decomposition_parents`;
  3. COEXISTENCE — if the parent has NO GitHub-native sub-issues yet
     (`total == 0`) but carries a `decomposition_parents` entry, falls back to
     the legacy hand-rolled check: each recorded child's state is queried via
     `gh issue view <child#> --json state` and the parent is closed only when
     EVERY recorded child is CLOSED;
  4. a parent whose native rollup is incomplete, or whose legacy fallback finds
     any child still OPEN (or unreadable), is left untouched (a no-op for that
     parent) and its key is retained.

`decomposition_parents` is a deprecating mirror honored during the coexistence
window so parents recorded before native sub-issue linking shipped keep
closing. Deprecation criterion: drop the `decomposition_parents` field and the
legacy hand-rolled fallback once no open parent carries an entry.

The step is IDEMPOTENT and a clean no-op when the map is empty/absent or the
state file is missing (the fresh-clone case): it makes no gh call and exits 0.
A parent already closed (its key already removed on a prior tick) is never
re-processed. The roll-up close is SCRIPT-BACKED (script > CLI > spec >
prompt), never a dispatcher judgment call.

  state_dir defaults to <cwd>/.rabbit
  state_dir is overridable via RABBIT_AUTO_EVOLVE_STATE_DIR (matching the
  sibling phase scripts).

`gh issue close` (not item-status.py) is used directly: a decomposed parent's
work landed across N child PRs, so there is no single merge commit SHA to
satisfy item-status.py's `--reason completed --commit-sha` gate; the roll-up
asserts completion from the sub-issue rollup evidence instead.

Exit code: 0 on success (including every no-op). Non-zero only on an
unexpected error closing a parent or persisting the updated state. A rollup or
child state that cannot be read is treated as "not complete" (the parent stays
open) and never fails the step.

Version: 1.1.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Add rabbit-issue/scripts to sys.path so `from _gh import repo_slug` works.
# Mirror the import style used by the sibling phase scripts (fetch-queue.py).
_HERE = Path(__file__).resolve().parent
_RABBIT_ISSUE_SCRIPTS = _HERE.parent.parent / "rabbit-issue" / "scripts"
if str(_RABBIT_ISSUE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RABBIT_ISSUE_SCRIPTS))
from _gh import repo_slug  # noqa: E402


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _state_path():
    return os.path.join(_state_dir(), "auto-evolve-state.json")


def _read_state():
    try:
        with open(_state_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_state(state):
    path = _state_path()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _native_rollup(parent):
    """Return the parent's GitHub-native sub-issue rollup as
    (total, completed), read from `gh api repos/{slug}/issues/<parent>` ->
    `sub_issues_summary`. Any read failure / unexpected payload returns
    (0, 0) — treated as "no native sub-issues" so the caller falls back to the
    legacy hand-rolled check rather than closing prematurely."""
    try:
        proc = subprocess.run(
            ["gh", "api", "repos/{}/issues/{}".format(repo_slug(), parent)],
            capture_output=True, text=True,
        )
    except OSError:
        return (0, 0)
    if proc.returncode != 0:
        return (0, 0)
    try:
        payload = json.loads(proc.stdout or "")
    except ValueError:
        return (0, 0)
    summary = payload.get("sub_issues_summary") or {}
    try:
        total = int(summary.get("total", 0))
        completed = int(summary.get("completed", 0))
    except (TypeError, ValueError):
        return (0, 0)
    return (total, completed)


def _child_closed(child):
    """True iff `gh issue view <child> --json state` reports CLOSED. Any read
    failure / unexpected payload is treated as NOT closed (parent stays open),
    so a transient gh error never closes a parent prematurely."""
    try:
        proc = subprocess.run(
            ["gh", "issue", "view", str(child), "--json", "state"],
            capture_output=True, text=True,
        )
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    try:
        payload = json.loads(proc.stdout or "")
    except ValueError:
        return False
    return str(payload.get("state", "")).upper() == "CLOSED"


def _parent_complete(parent, children):
    """Decide whether a decomposed parent is complete and ready to close.

    Prefers the AUTHORITATIVE GitHub-native sub-issue rollup: a parent with
    sub-issues (`total > 0`) is complete iff `completed == total`. COEXISTENCE
    fallback: a parent with no native sub-issues yet (`total == 0`) defers to
    the legacy hand-rolled per-child check — complete iff EVERY recorded child
    is CLOSED. A parent with no native sub-issues AND no recorded children is
    NOT complete (nothing to assert completion from)."""
    total, completed = _native_rollup(parent)
    if total > 0:
        return completed == total
    if children:
        return all(_child_closed(c) for c in children)
    return False


def _close_parent(parent, children):
    comment = (
        "Decomposed parent auto-closed by rabbit-auto-evolve (Inv 53): "
        "all decomposition children {} are closed.".format(
            ", ".join("#" + str(c) for c in children)
        )
    )
    proc = subprocess.run(
        ["gh", "issue", "close", str(parent),
         "--reason", "completed", "--comment", comment],
        capture_output=True, text=True,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode == 0


def run():
    state = _read_state()
    if not isinstance(state, dict):
        json.dump({"status": "noop", "closed": []}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    dp = state.get("decomposition_parents")
    if not isinstance(dp, dict) or not dp:
        json.dump({"status": "noop", "closed": []}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    closed = []
    failures = []
    # Iterate over a snapshot of keys so the dict can be mutated in-loop.
    for key in list(dp.keys()):
        children = dp.get(key) or []
        if not isinstance(children, list):
            continue
        try:
            parent_num = int(key)
        except (TypeError, ValueError):
            continue
        if not _parent_complete(parent_num, children):
            # Native rollup incomplete (or legacy fallback found an open/
            # unreadable child) -> leave the parent untouched.
            continue
        if _close_parent(parent_num, children):
            del dp[key]
            closed.append(parent_num)
        else:
            failures.append(parent_num)

    state["decomposition_parents"] = dp
    try:
        _write_state(state)
    except OSError as e:
        sys.stderr.write(f"close-decomposed-parents: cannot persist state: {e}\n")
        return 1

    result = {"status": "completed", "closed": closed}
    if failures:
        result["status"] = "failed"
        result["failed"] = failures
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if failures else 0


def main():
    argparse.ArgumentParser(
        description="Close every tracked decomposition parent whose "
                    "GitHub-native sub-issue rollup shows all sub-issues "
                    "complete (legacy hand-rolled per-child fallback during "
                    "coexistence), then drop its decomposition_parents key "
                    "(Inv 53). Idempotent; clean no-op when the map is "
                    "empty/absent."
    ).parse_args()
    return run()


if __name__ == "__main__":
    sys.exit(main())
