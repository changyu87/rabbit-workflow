#!/usr/bin/env python3
"""test-verification-hygiene.py — Inv 17.

Every test in rabbit-config/test/ MUST perform filesystem mutations only
inside a tempfile.TemporaryDirectory scope so that running the suite
never mutates the live workspace's .claude/ files.

  t17a: every other test file imports tempfile
  t17b: no test file references the live workspace path
        '.claude/settings.local.json' as a mutation target outside the
        context of a TemporaryDirectory tempdir variable
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SELF = os.path.basename(__file__)

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


test_files = sorted(
    f for f in os.listdir(TEST_DIR)
    if f.startswith("test-") and f.endswith(".py") and f != SELF
)

# t17a: every other test file imports tempfile (proxy for tempdir use)
missing_tempfile = []
for f in test_files:
    with open(os.path.join(TEST_DIR, f)) as fh:
        content = fh.read()
    if "import tempfile" not in content and "from tempfile" not in content:
        # Tests that don't touch the filesystem at all are allowed; tag
        # them as no-fs and ensure they make no open(..., 'w') calls.
        if re.search(r"open\([^)]*['\"]w['\"]", content):
            missing_tempfile.append(f)
if missing_tempfile:
    fail("17a", f"test files perform writes without importing tempfile: {missing_tempfile!r}")
else:
    ok("17a", f"all {len(test_files)} other test files either use tempfile or perform no writes")

# t17b: no test file opens a workspace-relative .claude/settings.local.json
# path for writing (must always be inside a tempdir).
offenders = []
for f in test_files:
    with open(os.path.join(TEST_DIR, f)) as fh:
        content = fh.read()
    for m in re.finditer(r"open\(([^)]+)\)", content):
        call_args = m.group(1)
        if ".claude/settings" in call_args and "'w'" in call_args:
            # Allow only when the path starts with a tempdir variable
            # (heuristic: open(os.path.join(td|tmp|... , ...).
            if not re.search(r"os\.path\.join\(\s*t[mp]?[a-z]*", call_args):
                offenders.append((f, m.group(0)))
if offenders:
    fail("17b", f"write calls to live workspace .claude/settings*: {offenders!r}")
else:
    ok("17b", "no writes to live workspace .claude/settings* outside tempdirs")

if FAIL:
    print("test-verification-hygiene: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-verification-hygiene: all checks passed.")
