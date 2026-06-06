#!/usr/bin/env python3
"""resolve-duplicate.py — record the GitHub-native duplicate resolution (Inv 60).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: drop the reinvented `duplicate` label read (the
  coexistence mirror) once no open or recently-closed issue carries the label
  and the native `state_reason=duplicate` is the sole expressed duplicate
  marker; retire the whole script if Claude Code / rabbit gains a native
  always-on autonomous-agent mode that supersedes rabbit-auto-evolve.

The duplicate-DETECTION heuristic stays in triage-issue.py rule 3 (the
case-folded title-substring match against closed-in-last-30-days issues, with
its confidence gate unchanged). This script owns only RESOLUTION: recording
the AUTHORITATIVE GitHub-native duplicate state for a duplicate the heuristic
has already confirmed.

Subcommands:
  resolve <dup#> <canonical#>
      Close <dup#> with the native duplicate state and cross-link <canonical#>:
        gh api --method PATCH repos/{slug}/issues/<dup#> \
          -f state=closed -f state_reason=duplicate
      then post ONE cross-reference comment naming <canonical#> so the native
      duplicate relationship is visible. The close is a TERMINAL convergence
      (spec Inv 25), never a label-strip-while-open de-queue. A NEW resolution
      NEVER stamps the reinvented `duplicate` label — only the native state.

  status <n>
      Report whether <n> is recognized as a duplicate, emitting JSON on stdout:
        {"issue": <n>, "is_duplicate": bool, "source": "native"|"legacy-label"|null}
      The native `stateReason == "duplicate"` is AUTHORITATIVE. The reinvented
      `duplicate` label is honored ONLY on read as a deprecating coexistence
      mirror (source "legacy-label"), so an in-flight issue stamped before the
      native cutover is still recognized.

Read/write surface (strictly bounded; reuses the
`gh api repos/{slug}/issues/...` access pattern Inv 53/58/59 already use):
  - `gh api --method PATCH repos/{slug}/issues/<dup#>` — native close-as-duplicate.
  - `gh issue comment <dup#>` — the cross-reference comment.
  - `gh issue view <n> --json state,stateReason,labels` — the status read.
Repo discovery uses rabbit-issue/_gh.repo_slug (a cross-scope INVOKE of the
shared gh helper, the same module triage-issue.py / fetch-queue.py bridge to;
rabbit-auto-evolve never edits rabbit-issue).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add rabbit-issue/scripts to sys.path so `from _gh import repo_slug` works
# (same bridge triage-issue.py uses).
_HERE = Path(__file__).resolve().parent
_RABBIT_ISSUE_SCRIPTS = _HERE.parent.parent / "rabbit-issue" / "scripts"
if str(_RABBIT_ISSUE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RABBIT_ISSUE_SCRIPTS))
from _gh import repo_slug  # noqa: E402

# The native close-reason enum value GitHub persists for a duplicate close.
_NATIVE_DUPLICATE = "duplicate"
# The reinvented label name, honored ONLY on read during the coexistence window.
_LEGACY_LABEL = "duplicate"


def _native_close_as_duplicate(slug, dup):
    """Close <dup> with the AUTHORITATIVE native duplicate state.

    `gh api --method PATCH repos/{slug}/issues/<dup> -f state=closed
    -f state_reason=duplicate`. Raises CalledProcessError on gh failure so the
    caller surfaces a non-zero exit (never silently leaves the issue open)."""
    subprocess.run(
        ["gh", "api", "--method", "PATCH",
         f"repos/{slug}/issues/{dup}",
         "-f", "state=closed",
         "-f", f"state_reason={_NATIVE_DUPLICATE}"],
        capture_output=True, text=True, check=True,
    )


def _cross_reference_comment(dup, canonical):
    """Post one cross-reference comment on <dup> naming the canonical issue, so
    the native duplicate relationship is visible. Raises on gh failure."""
    body = (
        f"Resolved as a duplicate of #{canonical} (native "
        f"`state_reason=duplicate`)."
    )
    subprocess.run(
        ["gh", "issue", "comment", str(dup),
         "--repo", repo_slug(),
         "--body", body],
        capture_output=True, text=True, check=True,
    )


def _issue_view(n):
    """`gh issue view <n> --json state,stateReason,labels` -> parsed dict.

    Raises CalledProcessError on gh failure."""
    proc = subprocess.run(
        ["gh", "issue", "view", str(n),
         "--repo", repo_slug(),
         "--json", "state,stateReason,labels"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout or "{}")


def cmd_resolve(args):
    dup = args.dup
    canonical = args.canonical
    slug = repo_slug()
    try:
        _native_close_as_duplicate(slug, dup)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(
            f"resolve-duplicate: native close-as-duplicate of #{dup} failed: "
            f"{e.stderr or e}\n")
        return 1
    try:
        _cross_reference_comment(dup, canonical)
    except subprocess.CalledProcessError as e:
        # The authoritative native state IS recorded; only the (derivative)
        # cross-reference comment failed. Report it but do not pretend success.
        sys.stderr.write(
            f"resolve-duplicate: native state recorded for #{dup} but the "
            f"cross-reference comment to #{canonical} failed: {e.stderr or e}\n")
        return 1
    print(json.dumps({
        "issue": dup,
        "resolved": True,
        "duplicate_of": canonical,
        "state_reason": _NATIVE_DUPLICATE,
    }))
    return 0


def cmd_status(args):
    n = args.issue
    try:
        view = _issue_view(n)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(
            f"resolve-duplicate: could not read issue #{n}: {e.stderr or e}\n")
        return 1
    except json.JSONDecodeError as e:
        sys.stderr.write(
            f"resolve-duplicate: issue #{n} returned non-JSON: {e}\n")
        return 1

    # Native state is AUTHORITATIVE.
    state_reason = (view.get("stateReason") or "").strip().lower()
    if state_reason == _NATIVE_DUPLICATE:
        print(json.dumps({"issue": n, "is_duplicate": True,
                          "source": "native"}))
        return 0

    # Deprecating coexistence mirror: honor the reinvented `duplicate` label on
    # read so an in-flight issue stamped before the native cutover is still
    # recognized. A NEW resolution never stamps it.
    label_names = {
        (lbl.get("name") or "") for lbl in (view.get("labels") or [])
    }
    if _LEGACY_LABEL in label_names:
        print(json.dumps({"issue": n, "is_duplicate": True,
                          "source": "legacy-label"}))
        return 0

    print(json.dumps({"issue": n, "is_duplicate": False, "source": None}))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(
        prog="resolve-duplicate.py",
        description="Record the GitHub-native duplicate resolution (Inv 60).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser(
        "resolve",
        help="close <dup> with native state_reason=duplicate and cross-link "
             "<canonical>")
    p_resolve.add_argument("dup", type=int,
                           help="the duplicate issue number to close")
    p_resolve.add_argument("canonical", type=int,
                           help="the canonical issue the duplicate resolves to")
    p_resolve.set_defaults(func=cmd_resolve)

    p_status = sub.add_parser(
        "status",
        help="report whether <n> is a recognized duplicate (native "
             "authoritative; legacy label honored on read)")
    p_status.add_argument("issue", type=int, help="the issue number to inspect")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
