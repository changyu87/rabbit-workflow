#!/usr/bin/env python3
"""test-vendored-mode-disambiguation-note.py

End-to-end content assertion that rabbit-cage's user-facing README documents
the terminology disambiguation: rabbit's vendored `.rabbit/` install
(historically called "plugin mode") is a DIFFERENT mechanism from Claude
Code's native `/plugin` marketplace plugins. Without this callout the two
unrelated senses of the word "plugin" collide and confuse readers.

The note lives in the README near the "Plugin mode" section. This is a
docs-only clarification — no rename, no behavior change.

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
README = os.path.join(FEATURE_DIR, "README.md")

# Substrings that together prove the disambiguation note is present. The note
# must name BOTH senses (rabbit's vendored install AND Claude Code's native
# /plugin marketplace plugins) and state they are unrelated/distinct.
REQUIRED_SUBSTRINGS = [
    "vendored",
    "/plugin",
    "marketplace plugins",
]
# At least one phrase asserting the two are NOT the same thing.
DISTINCTNESS_PHRASES = ["unrelated", "distinct", "different mechanism"]

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


if not os.path.isfile(README):
    fail("exist", f"missing surface: {README}")
else:
    with open(README) as f:
        body = f.read()
    for sub in REQUIRED_SUBSTRINGS:
        if sub in body:
            ok("substring", f"README contains: {sub!r}")
        else:
            fail("substring", f"README missing disambiguation substring: {sub!r}")
    if any(p in body for p in DISTINCTNESS_PHRASES):
        ok("distinctness", "README asserts the two mechanisms are distinct")
    else:
        fail("distinctness",
             f"README must assert distinctness via one of: {DISTINCTNESS_PHRASES}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-vendored-mode-disambiguation-note: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-vendored-mode-disambiguation-note: all checks passed.")
sys.exit(0)
