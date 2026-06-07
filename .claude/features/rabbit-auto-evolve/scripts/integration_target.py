#!/usr/bin/env python3
"""integration_target.py — resolve the loop's integration target branch
(Inv 61) with a dev<->main coexistence window.

The autonomous-evolve loop integrates merged work into a SINGLE resolved
"integration target" branch. The dev→main cutover is complete, so the resolved
target now defaults to `main`. A `dev` base is still ACCEPTED during the
coexistence teardown:

  - The RESOLVED target is `main` by default (the cutover is done and main is
    the live integration target) and can be overridden via the
    `RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET` env var. Any value outside the
    accepted set is an error.
  - The ACCEPTED set (what a PR base / current branch may be) is exactly
    `{dev, main}`; a base outside it is refused by merge-prs.py / safety-check.py.
  - The DEFAULT branch is `main`. GitHub's native `Fixes/Closes/Resolves`
    keyword auto-close fires only on a merge to the default branch, so the
    loop's manual close-after-merge is needed ONLY while the target is NOT the
    default branch (target=dev); once the target is main the native close
    fires and the manual path is redundant (see Inv 6 / Inv 61).

This module is imported by the sibling phase scripts (merge-prs.py,
safety-check.py, release-bump.py); it is resolved relative to its own
`__file__`, never via RABBIT_AUTO_EVOLVE_SCRIPT_DIR (which tests repoint at a
shim dir). It also runs as a small CLI that prints the resolved target.

Deprecation criterion: drop the coexistence accepted-set and the
`RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET` override once `main` is the sole
integration target after the cutover; the resolved target then becomes a
constant `main` and the manual close-after-merge path is removed.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import os
import sys

# The repo's default branch. GitHub native keyword auto-close fires only on a
# merge to this branch.
DEFAULT_BRANCH = "main"

# The coexistence accepted-set: a PR base / current branch may be either of
# these during the window. A base outside this set is refused.
ACCEPTED_TARGETS = ("dev", "main")

# The resolved target when no override is set (the post-cutover default; main
# is the live integration target).
DEFAULT_TARGET = "main"

ENV_VAR = "RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"


def accepted_targets():
    """Return the coexistence accepted-set as a tuple (dev, main)."""
    return ACCEPTED_TARGETS


def is_default_branch(target):
    """True iff `target` is the repo default branch (main), the branch where
    GitHub's native keyword auto-close fires."""
    return target == DEFAULT_BRANCH


def resolve_target():
    """Resolve the integration target: the `RABBIT_AUTO_EVOLVE_INTEGRATION_
    TARGET` env var when set, else the post-cutover default (main).

    Raises ValueError when the override is not one of the accepted targets —
    the loop refuses to integrate into an unrecognized branch."""
    override = os.environ.get(ENV_VAR)
    if override is None or override == "":
        return DEFAULT_TARGET
    if override not in ACCEPTED_TARGETS:
        raise ValueError(
            f"{ENV_VAR}={override!r} is not an accepted integration target; "
            f"expected one of {ACCEPTED_TARGETS}"
        )
    return override


def main():
    parser = argparse.ArgumentParser(
        description="Print the loop's resolved integration target branch "
                    "(dev<->main coexistence; default main, overridable via "
                    f"{ENV_VAR}). Exits non-zero on an unrecognized override.",
    )
    parser.parse_args()
    try:
        sys.stdout.write(resolve_target() + "\n")
    except ValueError as e:
        sys.stderr.write(f"integration_target: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
