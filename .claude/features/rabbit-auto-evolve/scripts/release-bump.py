#!/usr/bin/env python3
"""release-bump.py — apply the design-doc §9 semver bump table for a merged PR.

Usage:
  release-bump.py <pr#> [--features-threshold N]

Per rabbit-auto-evolve spec.md Inv 7, this script:

  1. Fetches the merged PR's metadata via
     `gh pr view <#> --json number,title,labels,body,files`.
  2. Applies the bump table (major triggers override minor/patch):
       - body contains literal 'bump:major'    → major / body-directive
       - >= N distinct top-level features touched
         (N defaults to 3; --features-threshold N override)
                                               → major / feature-count-threshold
       - any file under .claude/features/contract/schemas/ touched
                                               → major / contract-schema-touch
       - priority:high or priority:critical    → minor / priority-high-critical
       - priority:low or priority:medium       → patch / priority-low-medium
     Priority source (Inv 46): an explicit priority:<level> label ON the
     PR wins. When the PR has none, resolve the closing issue from the PR
     body (`Fixes|Closes|Resolves #N`, case-insensitive) and read THAT
     issue's priority:<level> label via `gh issue view <N> --json labels`
     — the dispatch flow opens PRs without copying the source issue's
     priority label. Major triggers above are evaluated first and are
     unaffected.
     If no priority label and no major trigger → patch / priority-low-medium
     (safe default; the loop progresses rather than wedging).
  3. Reads the prior tag via `git describe --tags --abbrev=0` and computes
     next_tag. When the repo has zero tags (first-release case, issue
     #400) `git describe` exits non-zero — this is NOT an error: prior_tag
     is null and next_tag is the fixed first-release tag v1.0.0 (the bump
     table only governs how an EXISTING version is incremented). Otherwise
     next_tag is the prior tag bumped per the table.
  4. Calls `safety-check.py <pr#> --phase release --next-tag <next_tag>`
     BEFORE any git operation (resolved Open Question 2: --next-tag flag,
     not env var). Non-zero exit → emit {status:skipped,
     reason:safety-check-failed} and stop (no git mutation, exit 0).
  5. Otherwise: `git tag -a <next_tag> -m <auto-evolve msg>`,
     `git push origin <next_tag>`,
     `gh release create <next_tag> --notes-from-tag --target dev`.

Emits a single JSON object on stdout (prior_tag is null on first release):
  {
    "pr": 348,
    "prior_tag": "v0.5.2",
    "next_tag": "v0.5.3",
    "bump": "patch",
    "trigger": "priority-low-medium",
    "status": "released" | "skipped" | "failed",
    "reason": "<short>"
  }

Exit 0 always except argparse / unexpected error.

On a `released` status this script also writes the cut `next_tag` into
`last_tagged_version` in `<state_dir>/auto-evolve-state.json` (issue #564):
read-modify-write, atomic via temp+rename, mirroring the pattern merge-prs.py
uses for `pending_post_merge` / `last_merged_sha`. No phase script previously
persisted this informational field (surfaced by status-report.py), so it
lagged perpetually; phase 10's deterministic re-read (update-state.py,
Inv 40) now captures it off disk — it is never dispatcher hand-set. A
skipped/failed run leaves the field untouched. The state dir resolves via
RABBIT_AUTO_EVOLVE_STATE_DIR when set, else `<cwd>/.rabbit`.

The sibling `safety-check.py` is resolved via RABBIT_AUTO_EVOLVE_SCRIPT_DIR
when set; otherwise via this script's own dirname (mirrors merge-prs.py and
cleanup-branches.py).

Version: 1.3.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import re
import subprocess
import sys


CONTRACT_SCHEMAS_PREFIX = ".claude/features/contract/schemas/"
FEATURE_PREFIX = ".claude/features/"

# Closing-issue reference in a PR body: "Fixes|Closes|Resolves #N"
# (case-insensitive). First match wins (Inv 46, issue #529).
_CLOSING_RE = re.compile(r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\b"
                         r"\s+#(\d+)", re.IGNORECASE)

_PRIORITY_LABELS = ("priority:critical", "priority:high",
                    "priority:low", "priority:medium")


def _script_dir():
    return os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
                          os.path.dirname(os.path.abspath(__file__)))


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _record_last_tagged_version(next_tag):
    """Write `next_tag` into `last_tagged_version` in the on-disk state file
    (issue #564). Read-modify-write, atomic via temp+rename, mirroring the
    pattern merge-prs.py uses for `pending_post_merge` / `last_merged_sha`.

    Called ONLY on a `released` status — a skipped/failed run leaves the
    field untouched. Best-effort: a missing/malformed state file or write
    error emits a stderr warning and never fails the release (the result
    JSON on stdout is the authoritative outcome). Phase 10's deterministic
    re-read (update-state.py, Inv 40) later captures it off disk — it is
    never dispatcher hand-set."""
    state_path = os.path.join(_state_dir(), "auto-evolve-state.json")
    try:
        with open(state_path) as f:
            state = json.load(f)
    except (OSError, ValueError) as e:
        sys.stderr.write(
            f"release-bump: cannot read state file {state_path}: {e}\n"
        )
        return
    state["last_tagged_version"] = next_tag
    tmp_path = state_path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, state_path)
    except OSError as e:
        sys.stderr.write(f"release-bump: state write failed: {e}\n")
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _fetch_pr(pr):
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr),
         "--json", "number,title,labels,body,files"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh pr view failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _label_names(payload):
    return {lbl.get("name", "") for lbl in payload.get("labels", [])}


def _file_paths(payload):
    return [f.get("path", "") for f in payload.get("files", [])]


def _distinct_features(paths):
    """Distinct second path segments under .claude/features/."""
    feats = set()
    for p in paths:
        if not p.startswith(FEATURE_PREFIX):
            continue
        parts = p.split("/")
        # ['.claude', 'features', '<name>', ...]
        if len(parts) >= 3 and parts[2]:
            feats.add(parts[2])
    return feats


def _has_priority(labels):
    """True when `labels` carries any priority:<level> label."""
    return any(p in labels for p in _PRIORITY_LABELS)


def _closing_issue(body):
    """First Fixes|Closes|Resolves #N issue number in `body`, or None."""
    m = _CLOSING_RE.search(body or "")
    return int(m.group(1)) if m else None


def _issue_labels(issue):
    """Label-name set for issue #<issue> via gh, or empty set on failure.

    A missing / unresolvable issue (gh exits non-zero) is NOT an error here:
    it just means there is no fallback priority, so the bump table keeps its
    default (Inv 46, issue #529).
    """
    proc = subprocess.run(
        ["gh", "issue", "view", str(issue), "--json", "labels"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return set()
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return set()
    return _label_names(payload)


def classify(payload, features_threshold):
    """Apply the bump table; return (bump, trigger)."""
    body = payload.get("body") or ""
    labels = _label_names(payload)
    paths = _file_paths(payload)

    # Major triggers (top-down; first match wins).
    if "bump:major" in body:
        return ("major", "body-directive")

    distinct = _distinct_features(paths)
    if len(distinct) >= features_threshold:
        return ("major", "feature-count-threshold")

    if any(p.startswith(CONTRACT_SCHEMAS_PREFIX) for p in paths):
        return ("major", "contract-schema-touch")

    # Priority source (Inv 46, issue #529): an explicit priority label ON the
    # PR wins. Only when the PR has none do we fall back to the closing
    # issue's priority (the dispatch flow opens PRs without the source issue's
    # priority label). Major triggers above are evaluated first and unaffected.
    if not _has_priority(labels):
        issue = _closing_issue(body)
        if issue is not None:
            labels = labels | _issue_labels(issue)

    if "priority:high" in labels or "priority:critical" in labels:
        return ("minor", "priority-high-critical")

    # priority:low / priority:medium / missing priority → patch (safe default).
    return ("patch", "priority-low-medium")


FIRST_RELEASE_TAG = "v1.0.0"


def _prior_tag():
    """Return the most recent tag, or None when the repo has zero tags.

    `git describe --tags --abbrev=0` exits non-zero ("fatal: No names
    found, cannot describe anything.") in a tag-free repo. That is the
    first-release case (issue #400), NOT an error: returning None lets
    `run()` cut the very first release at FIRST_RELEASE_TAG instead of
    crashing and silently skipping Phase 7.
    """
    proc = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _compute_next_tag(prior_tag, bump):
    """Bump prior_tag (vX.Y.Z) → next_tag (vX'.Y'.Z') per `bump`."""
    raw = prior_tag.lstrip("v")
    parts = raw.split(".")
    if len(parts) != 3:
        raise RuntimeError(f"prior tag {prior_tag!r} not in vX.Y.Z form")
    try:
        x, y, z = (int(p) for p in parts)
    except ValueError as e:
        raise RuntimeError(f"prior tag {prior_tag!r} not numeric: {e}")
    if bump == "major":
        return f"v{x + 1}.0.0"
    if bump == "minor":
        return f"v{x}.{y + 1}.0"
    return f"v{x}.{y}.{z + 1}"


def _safety_check(pr, next_tag):
    safety = os.path.join(_script_dir(), "safety-check.py")
    return subprocess.run(
        [sys.executable, safety, str(pr),
         "--phase", "release", "--next-tag", next_tag],
        capture_output=True, text=True,
    )


def _git_tag(next_tag, pr, title):
    msg = f"auto-evolve #{pr} {title}"
    return subprocess.run(
        ["git", "tag", "-a", next_tag, "-m", msg],
        capture_output=True, text=True,
    )


def _git_push_tag(next_tag):
    return subprocess.run(
        ["git", "push", "origin", next_tag],
        capture_output=True, text=True,
    )


def _gh_release(next_tag):
    return subprocess.run(
        ["gh", "release", "create", next_tag,
         "--notes-from-tag", "--target", "dev"],
        capture_output=True, text=True,
    )


def run(pr, features_threshold):
    payload = _fetch_pr(pr)
    bump, trigger = classify(payload, features_threshold)
    prior_tag = _prior_tag()
    if prior_tag is None:
        # First release (zero prior tags): the bump table only governs how
        # an EXISTING version is incremented, so it does not apply here.
        # Start the version line at the fixed first-release tag (issue #400).
        next_tag = FIRST_RELEASE_TAG
    else:
        next_tag = _compute_next_tag(prior_tag, bump)

    result = {
        "pr": pr,
        "prior_tag": prior_tag,
        "next_tag": next_tag,
        "bump": bump,
        "trigger": trigger,
    }

    sc = _safety_check(pr, next_tag)
    if sc.returncode != 0:
        result["status"] = "skipped"
        result["reason"] = "safety-check-failed"
        return result

    title = payload.get("title") or ""
    tag_res = _git_tag(next_tag, pr, title)
    if tag_res.returncode != 0:
        result["status"] = "failed"
        result["reason"] = f"git-tag-failed: {tag_res.stderr.strip()}"
        return result

    push_res = _git_push_tag(next_tag)
    if push_res.returncode != 0:
        result["status"] = "failed"
        result["reason"] = f"git-push-failed: {push_res.stderr.strip()}"
        return result

    rel_res = _gh_release(next_tag)
    if rel_res.returncode != 0:
        result["status"] = "failed"
        result["reason"] = f"gh-release-failed: {rel_res.stderr.strip()}"
        return result

    result["status"] = "released"
    result["reason"] = ""
    # Persist the cut tag to on-disk state (issue #564). Phase 10's
    # deterministic re-read (update-state.py, Inv 40) captures it next tick.
    _record_last_tagged_version(next_tag)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Apply the §9 semver bump table for a merged PR and "
                    "(after safety-check) create the annotated tag and "
                    "GitHub release. Emits a single result JSON object on "
                    "stdout; exits 0 always except argparse/unexpected error."
    )
    parser.add_argument("pr", type=int, help="merged PR number")
    parser.add_argument(
        "--features-threshold", type=int, default=3,
        help="distinct top-level feature directories touched threshold for "
             "the major-bump rule (default: 3)",
    )
    args = parser.parse_args()

    result = run(args.pr, args.features_threshold)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
