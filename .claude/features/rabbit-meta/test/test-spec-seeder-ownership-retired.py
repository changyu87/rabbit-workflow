#!/usr/bin/env python3
"""test-spec-seeder-ownership-retired.py — issue #706 (under #639).

End-to-end content test that rabbit-meta's live doc surface (docs/spec.md) no
longer carries the STALE spec-seeder ownership claim in its "What this feature
does NOT define" section.

Verified reality (deterministic, #706):
  - `.claude/features/spec-seeder/` does NOT exist (absorbed into rabbit-spec).
  - rabbit-spec/docs/spec.md owns the spec-lifecycle / spec-drafting role
    (rabbit-spec-create + the rabbit-spec-creator subagent).
  - `rabbit-feature-new` is a stale skill name; the live skill is
    `rabbit-feature-scaffold`.

The original line read:
  "The spec-seeding subagent invoked by `rabbit-feature-new` — owned by the
   `spec-seeder` feature."

Both the `spec-seeder` feature and the `rabbit-feature-new` skill are dead
references. This guard scans rabbit-meta's OWN spec surface and fails if the
stale ownership claim (the `spec-seeder` feature owning the spec-seeding role)
is still present.

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# The dead `spec-seeder` feature must not be named anywhere in the live spec
# surface (the only reference was the stale ownership exclusion).
SPEC_SEEDER_RE = re.compile(r"spec-seeder", re.IGNORECASE)

# The stale skill name `rabbit-feature-new` must not appear on a line that
# also names the spec-seeding role (the stale exclusion line). Other
# `rabbit-feature-new` references (killer-story prose, path-glob enhancement)
# are out of #706 scope and left untouched.
STALE_OWNERSHIP_RE = re.compile(
    r"spec-seed.*rabbit-feature-new|rabbit-feature-new.*spec-seed",
    re.IGNORECASE,
)

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


if not os.path.isfile(SPEC):
    fail("exist", f"missing surface: {SPEC}")
else:
    seeder_hits = []
    ownership_hits = []
    with open(SPEC) as f:
        for lineno, line in enumerate(f, start=1):
            if SPEC_SEEDER_RE.search(line):
                seeder_hits.append((lineno, line.rstrip()))
            if STALE_OWNERSHIP_RE.search(line):
                ownership_hits.append((lineno, line.rstrip()))

    if seeder_hits:
        for lineno, content in seeder_hits:
            fail("spec-seeder-dead",
                 f"line {lineno}: dead `spec-seeder` feature reference: {content}")
    else:
        ok("spec-seeder-dead",
           "no dead `spec-seeder` feature reference in docs/spec.md")

    if ownership_hits:
        for lineno, content in ownership_hits:
            fail("stale-ownership",
                 f"line {lineno}: stale spec-seeding ownership claim: {content}")
    else:
        ok("stale-ownership",
           "no stale spec-seeding ownership claim in docs/spec.md")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-seeder-ownership-retired: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-seeder-ownership-retired: all checks passed.")
sys.exit(0)
