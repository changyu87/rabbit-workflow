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
     If no priority label and no major trigger → patch / priority-low-medium
     (safe default; the loop progresses rather than wedging).
  3. Computes next_tag from `git describe --tags --abbrev=0` (prior tag).
  4. Calls `safety-check.py <pr#> --phase release --next-tag <next_tag>`
     BEFORE any git operation (resolved Open Question 2: --next-tag flag,
     not env var). Non-zero exit → emit {status:skipped,
     reason:safety-check-failed} and stop (no git mutation, exit 0).
  5. Otherwise: `git tag -a <next_tag> -m <auto-evolve msg>`,
     `git push origin <next_tag>`,
     `gh release create <next_tag> --notes-from-tag --target dev`.

Emits a single JSON object on stdout:
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

The sibling `safety-check.py` is resolved via RABBIT_AUTO_EVOLVE_SCRIPT_DIR
when set; otherwise via this script's own dirname (mirrors merge-prs.py and
cleanup-branches.py).

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys


CONTRACT_SCHEMAS_PREFIX = ".claude/features/contract/schemas/"
FEATURE_PREFIX = ".claude/features/"


def _script_dir():
    return os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
                          os.path.dirname(os.path.abspath(__file__)))


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

    if "priority:high" in labels or "priority:critical" in labels:
        return ("minor", "priority-high-critical")

    # priority:low / priority:medium / missing priority → patch (safe default).
    return ("patch", "priority-low-medium")


def _prior_tag():
    proc = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git describe failed: {proc.stderr.strip()}")
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
