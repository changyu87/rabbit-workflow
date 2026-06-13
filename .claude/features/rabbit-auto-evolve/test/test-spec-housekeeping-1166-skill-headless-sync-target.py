#!/usr/bin/env python3
"""test-spec-housekeeping-1166-skill-headless-sync-target.py — issue #1166.

End-to-end content regression that rabbit-auto-evolve's SOURCE SKILL.md
headless-tick sync example reflects the CURRENT dynamic integration-target
resolution rather than the old hardcoded/coexistence-era `origin/dev` form.

Before integration_target.py, the headless tick-start self-sync was documented
as a hardcoded `git pull --ff-only origin dev`. The dev->main cutover is now
complete (integration_target.py `resolve_target()` returns `main`
deterministically, no env, no override), so the sync step resolves the
integration target dynamically and runs `git pull --ff-only origin
<integration-target>` (currently `origin main`).

The #639 checks that prove the banned wording dead:

  - "dev default, main post-cutover" — symbol/behavior check:
    integration_target.py `resolve_target()` reads no env and returns `main`
    constantly; the dev<->main coexistence window has CLOSED, so the
    "dev default" / "post-cutover" coexistence narration is stale. The
    normative dynamic-resolution sentence survives.

This test pins:
  1. The stale coexistence wording is ABSENT from the source SKILL.md.
  2. The source SKILL.md headless-sync prose still documents the dynamic
     resolution: `sync-tree.py`, `<integration-target>`, the
     `integration_target.py`/`resolve_target` resolver, and `git pull
     --ff-only` (never `git merge`).

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SKILL = os.path.join(
    FEATURE_DIR, "skills", "rabbit-auto-evolve", "SKILL.md"
)

# Verbatim stale coexistence-era wording that MUST be absent from the source
# SKILL.md (the headless-sync example must not imply a dev-default/coexistence
# integration target).
BANNED_PHRASES = [
    "dev default, main post-cutover",
]

# Required dynamic-resolution phrases (normalized whitespace, lowercased).
REQUIRED_PHRASES = [
    "sync-tree.py",
    "<integration-target>",
    "git pull --ff-only origin <integration-target>",
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


if not os.path.isfile(SKILL):
    fail("exist", f"missing surface: {SKILL}")
else:
    with open(SKILL) as f:
        raw = f.read()
    flat = norm(raw)
    flat_low = flat.lower()

    for phrase in BANNED_PHRASES:
        if phrase.lower() in flat_low:
            fail(
                "stale-prose",
                f"stale coexistence wording still in SKILL.md: {phrase!r}",
            )
        else:
            ok("stale-prose", f"absent: {phrase!r}")

    for phrase in REQUIRED_PHRASES:
        if phrase.lower() in flat_low:
            ok("dynamic-resolution", f"present: {phrase!r}")
        else:
            fail(
                "dynamic-resolution",
                f"SKILL.md headless-sync prose missing: {phrase!r}",
            )

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print(
        "test-spec-housekeeping-1166-skill-headless-sync-target: FAIL",
        file=sys.stderr,
    )
    sys.exit(1)

print(
    "test-spec-housekeeping-1166-skill-headless-sync-target: "
    "all checks passed."
)
sys.exit(0)
