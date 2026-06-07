#!/usr/bin/env python3
"""integration_target.py — resolve the loop's integration target branch
(Inv 61).

The autonomous-evolve loop integrates merged work into a SINGLE resolved
"integration target" branch. The dev->main cutover is complete and the
`dev`<->`main` coexistence window has CLOSED: `main` is now the SOLE integration
target.

  - The RESOLVED target is `main`, deterministically — `resolve_target()` reads
    no environment and takes no override.
  - The ACCEPTED set (what a PR base / current branch may be) is exactly
    `{main}`; a base outside it is refused by merge-prs.py / safety-check.py.
  - `main` is the repo DEFAULT branch. GitHub's native `Fixes/Closes/Resolves`
    keyword auto-close fires on every merge into it, so the loop relies entirely
    on native auto-close — there is no longer any manual close-after-merge path
    (see Inv 6 / Inv 61).

This module is imported by the sibling phase scripts (merge-prs.py,
safety-check.py, release-bump.py); it is resolved relative to its own
`__file__`, never via RABBIT_AUTO_EVOLVE_SCRIPT_DIR (which tests repoint at a
shim dir). It also runs as a small CLI that prints the resolved target.

Version: 2.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: a future change to rabbit's integration branch model
(e.g. a new release branch the loop must target) supersedes this single-target
abstraction; until then `main` is the sole, constant integration target.
"""

import argparse
import sys

# The repo's default branch and the sole integration target. GitHub native
# keyword auto-close fires on every merge into it.
DEFAULT_BRANCH = "main"

# The accepted-set: a PR base / current branch must be the sole integration
# target. A base outside this set is refused.
ACCEPTED_TARGETS = ("main",)


def accepted_targets():
    """Return the accepted-set as a tuple — `('main',)`."""
    return ACCEPTED_TARGETS


def is_default_branch(target):
    """True iff `target` is the repo default branch (main), the branch where
    GitHub's native keyword auto-close fires."""
    return target == DEFAULT_BRANCH


def resolve_target():
    """Resolve the integration target. The cutover is complete and the
    coexistence window has closed, so this is deterministically `main` — no
    environment is read and no override is honored."""
    return DEFAULT_BRANCH


def main():
    parser = argparse.ArgumentParser(
        description="Print the loop's resolved integration target branch "
                    "(always main; the dev<->main coexistence window has "
                    "closed).",
    )
    parser.parse_args()
    sys.stdout.write(resolve_target() + "\n")


if __name__ == "__main__":
    main()
