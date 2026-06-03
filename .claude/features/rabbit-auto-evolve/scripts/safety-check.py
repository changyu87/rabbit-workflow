#!/usr/bin/env python3
"""safety-check.py — enforce the five bottom-line safety invariants (Inv 5).

Usage:
  safety-check.py <pr#> --phase {merge|release|cleanup} [--next-tag vX.Y.Z]

Per rabbit-auto-evolve spec.md Inv 5, the script enforces the bottom-line
safety invariants from design doc §9 before any merge / release / cleanup
action runs. Each numbered invariant is gated to specific phases:

  Invariant 1 — current git branch is `dev`             (merge, release, cleanup)
  Invariant 2 — PR base branch is `dev`                 (merge, release)
  Invariant 3 — PR head matches ^feat/.+ and is not
                `dev`, `main`, or `release/...`         (cleanup)
  Invariant 4 — the --next-tag tag does not exist       (release)
  Invariant 5 — no uncommitted tracked-file modifications  (merge, release, cleanup)

`--next-tag vX.Y.Z` is REQUIRED iff `--phase release`, FORBIDDEN otherwise
(resolved Open Question 2).

Exit code: 0 on pass; non-zero on any violation. On violation, every
violated invariant is emitted on stderr as:
  Invariant N (<short>) failed: <detail>
The script never auto-fixes.

The script reads `gh` and `git` state only — no filesystem mutations.

Version: 1.1.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import re
import subprocess
import sys


PHASES = ("merge", "release", "cleanup")

# Phase -> ordered list of invariant numbers to enforce.
INV_BY_PHASE = {
    "merge":   [1, 2, 5],
    "release": [1, 2, 4, 5],
    "cleanup": [1, 3, 5],
}

# Short names for stderr reporting.
INV_SHORT = {
    1: "branch is dev",
    2: "PR base is dev",
    3: "PR head matches ^feat/.+",
    4: "next-tag does not exist",
    5: "no uncommitted tracked-file modifications",
}


def _git(*args):
    """Run `git` and return (returncode, stdout, stderr) as text."""
    proc = subprocess.run(
        ["git", *args], capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _gh(*args):
    """Run `gh` and return (returncode, stdout, stderr) as text."""
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def check_inv_1(args):
    """Current git branch is `dev`."""
    rc, out, err = _git("rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0:
        return f"git rev-parse failed: {err.strip()}"
    branch = out.strip()
    if branch != "dev":
        return f"current branch is {branch!r}, expected 'dev'"
    return None


def check_inv_2(args):
    """PR base branch (gh pr view) is `dev`."""
    rc, out, err = _gh(
        "pr", "view", str(args.pr),
        "--json", "baseRefName", "-q", ".baseRefName",
    )
    if rc != 0:
        return f"gh pr view failed: {err.strip()}"
    base = out.strip()
    if base != "dev":
        return f"PR base is {base!r}, expected 'dev'"
    return None


def check_inv_3(args):
    """PR head branch matches ^feat/.+ and is not dev/main/release/..."""
    rc, out, err = _gh(
        "pr", "view", str(args.pr),
        "--json", "headRefName", "-q", ".headRefName",
    )
    if rc != 0:
        return f"gh pr view failed: {err.strip()}"
    head = out.strip()
    if head in ("dev", "main"):
        return f"head is {head!r}; must not be 'dev' or 'main'"
    if head.startswith("release/"):
        return f"head is {head!r}; must not start with 'release/'"
    if not re.match(r"^feat/.+", head):
        return f"head is {head!r}; does not match '^feat/.+'"
    return None


def check_inv_4(args):
    """The --next-tag tag does not already exist."""
    tag = args.next_tag
    # `git rev-parse --verify --quiet <tag>^{}` exits 0 iff tag exists.
    rc, _out, _err = _git(
        "rev-parse", "--verify", "--quiet", f"{tag}^{{}}",
    )
    if rc == 0:
        return f"tag {tag!r} already exists"
    return None


def check_inv_5(args):
    """No uncommitted modifications to tracked files (staged or unstaged).

    Untracked files (`??`) cannot affect a merge, so they are intentionally
    ignored (issue #397): `git status --porcelain` reported them and
    deadlocked the auto-evolve loop every time a new runtime artifact
    appeared. Two `git diff --quiet` calls catch M/A/D/R on tracked files:
    `git diff --quiet` exits non-zero on any unstaged tracked change;
    `git diff --cached --quiet` exits non-zero on any staged change.
    """
    unstaged = _git("diff", "--quiet")[0]
    staged = _git("diff", "--cached", "--quiet")[0]
    if unstaged != 0:
        return "tracked file has unstaged modifications"
    if staged != 0:
        return "tracked file has staged modifications"
    return None


CHECKS = {
    1: check_inv_1,
    2: check_inv_2,
    3: check_inv_3,
    4: check_inv_4,
    5: check_inv_5,
}


def main():
    parser = argparse.ArgumentParser(
        description="Enforce the five bottom-line safety invariants before "
                    "any merge / release / cleanup action runs. Exits "
                    "non-zero on any violation; never auto-fixes."
    )
    parser.add_argument("pr", type=int, help="PR number")
    parser.add_argument(
        "--phase", choices=PHASES, required=True,
        help="which gating set to enforce",
    )
    parser.add_argument(
        "--next-tag", default=None,
        help="next release tag (e.g. v1.2.3). REQUIRED iff --phase release; "
             "FORBIDDEN otherwise.",
    )
    args = parser.parse_args()

    if args.phase == "release" and not args.next_tag:
        parser.error("--next-tag required for --phase release")
    if args.phase != "release" and args.next_tag:
        parser.error(f"--next-tag forbidden for --phase {args.phase}")

    violations = []
    for n in INV_BY_PHASE[args.phase]:
        detail = CHECKS[n](args)
        if detail is not None:
            violations.append((n, detail))

    if violations:
        for n, detail in violations:
            sys.stderr.write(
                f"Invariant {n} ({INV_SHORT[n]}) failed: {detail}\n"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
