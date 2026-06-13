#!/usr/bin/env python3
"""test-spec-housekeeping-1167-resync-comment-target.py — issue #1167.

Content regression that run-tick-phases.py's tick docstring describing the
post-merge re-sync step reflects the CURRENT target-aware sync behavior rather
than the old coexistence-era hardcoded `origin/dev` form.

Before integration_target.py, the post-merge re-sync was documented in the
module docstring's post-dispatch phase narration as a re-sync "to origin/dev".
The dev->main cutover is now complete (integration_target.py `resolve_target()`
returns `main` deterministically), and the re-sync reuses `sync-tree.py`, which
resolves the integration target via `integration_target.py` `resolve_target()`
and runs `git pull --ff-only origin <resolved-target>`. The stale `origin/dev`
wording in the docstring is dead.

This test pins:
  1. The stale `origin/dev` wording is ABSENT from the source script
     run-tick-phases.py.
  2. The script's docstring still documents the dynamic resolution: it names
     `sync-tree.py`, the `integration_target.py`/`resolve_target` resolver,
     and the resolved-target phrasing.

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "run-tick-phases.py")

# Verbatim stale coexistence-era wording that MUST be absent from the source
# script (the post-merge re-sync narration must not name a hardcoded
# `origin/dev` integration target).
BANNED_PHRASES = [
    "origin/dev",
]

# Required dynamic-resolution phrases (normalized whitespace, lowercased).
REQUIRED_PHRASES = [
    "sync-tree.py",
    "integration_target.py",
    "resolve_target",
]

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def norm(text):
    return re.sub(r"\s+", " ", text)


if not os.path.isfile(SCRIPT):
    fail("exist", f"missing surface: {SCRIPT}")
else:
    with open(SCRIPT) as f:
        raw = f.read()
    flat = norm(raw)
    flat_low = flat.lower()

    for phrase in BANNED_PHRASES:
        if phrase.lower() in flat_low:
            fail(
                "stale-prose",
                f"stale coexistence wording still in run-tick-phases.py: "
                f"{phrase!r}",
            )
        else:
            ok("stale-prose", f"absent: {phrase!r}")

    for phrase in REQUIRED_PHRASES:
        if phrase.lower() in flat_low:
            ok("dynamic-resolution", f"present: {phrase!r}")
        else:
            fail(
                "dynamic-resolution",
                f"run-tick-phases.py docstring missing: {phrase!r}",
            )

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print(
        "test-spec-housekeeping-1167-resync-comment-target: FAIL",
        file=sys.stderr,
    )
    sys.exit(1)

print(
    "test-spec-housekeeping-1167-resync-comment-target: all checks passed."
)
sys.exit(0)
