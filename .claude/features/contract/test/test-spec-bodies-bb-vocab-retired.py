#!/usr/bin/env python3
"""test-spec-bodies-bb-vocab-retired.py — issue #661 (part of #420).

End-to-end content test that contract's live docs/spec.md and docs/contract.md
no longer carry legacy bug-and-backlog ("B/B") LIVE vocabulary as current
prose. The retired bug-and-backlog system was succeeded by the rabbit-issue
system; doc surfaces describe the current design, so they must speak the
current vocabulary ("issue", "bug or enhancement"),
NOT the retired "B/B" / "bug-and-backlog" / "bug/backlog" / standalone
"backlog" terms.

This is a regression guard for the prove-it-dead retirement, not an Inv 41
strict-tier check (which already bans #NNN and tombstone language). It scans
contract's OWN live doc surfaces line by line, flagging current-usage B/B
prose tokens. A small ALLOWLIST exempts load-bearing literals that legitimately
contain these tokens and CANNOT be reworded without making the spec inaccurate:

  - the `bug-backlog-files` git branch name (the actual storage branch where
    rabbit-files live; referenced verbatim across features), and
  - the `BACKLOG-[0-9]` / "BACKLOG-N" regex tokens enforced by Inv 41's
    baseline tier (the literal pattern the checker matches).

Allowlist entries are matched by (relative_path, substring) so a token only
escapes the ban when it appears as part of one of these known literals.

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")
CONTRACT = os.path.join(FEATURE_DIR, "docs", "contract.md")

# Case-insensitive current-usage B/B vocabulary tokens that must not appear as
# live prose in contract's doc surfaces.
BANNED = [
    r"\bB/B\b",
    r"bug-and-backlog",
    r"bug and backlog",
    r"bug-backlog",
    r"bug/backlog",
    r"\bbacklog\b",
]
_BANNED_RE = re.compile("|".join(BANNED), re.IGNORECASE)

# Load-bearing literals that legitimately contain a banned token. A flagged
# occurrence is exempt iff one of these substrings (for the same file) covers
# the match. These cannot be reworded without making the surface inaccurate.
ALLOWLIST = {
    "docs/spec.md": [
        # The actual git branch name where rabbit-files are stored.
        "bug-backlog-files",
        # Inv 41 baseline-tier regex tokens — the literal patterns enforced.
        "BACKLOG-[0-9]",
        "BACKLOG-N",
    ],
}

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


def scan(path, rel):
    """Return list of (lineno, token, line) with a non-allowlisted match."""
    allowed = ALLOWLIST.get(rel, [])
    violations = []
    with open(path) as f:
        for lineno, line in enumerate(f, start=1):
            for m in _BANNED_RE.finditer(line):
                start, end = m.span()
                # Exempt if the match falls within any allowlisted literal on
                # this line.
                exempt = False
                for lit in allowed:
                    for am in re.finditer(re.escape(lit), line):
                        if am.start() <= start and end <= am.end():
                            exempt = True
                            break
                    if exempt:
                        break
                if not exempt:
                    violations.append((lineno, m.group(0), line.rstrip()))
    return violations


for path, rel in ((SPEC, "docs/spec.md"), (CONTRACT, "docs/contract.md")):
    if not os.path.isfile(path):
        fail("exist", f"missing surface: {path}")
        continue
    v = scan(path, rel)
    if v:
        for lineno, tok, content in v:
            fail(rel, f"line {lineno}: live B/B token '{tok}': {content}")
    else:
        ok(rel, "no live bug-and-backlog vocabulary")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-bodies-bb-vocab-retired: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-bodies-bb-vocab-retired: all checks passed.")
sys.exit(0)
