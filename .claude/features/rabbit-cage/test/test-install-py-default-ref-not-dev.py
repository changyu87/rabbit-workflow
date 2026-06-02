#!/usr/bin/env python3
"""rabbit-cage regression — install.py HARDCODED_STABLE_DEFAULT MUST be a stable channel.

Bug #286 / spec Inv 29: install.py's hardcoded default upstream ref MUST match
a stable release branch (`release/[0-9]+\\.[0-9]+`) or a semver tag
(`v[0-9]+\\.[0-9]+\\.[0-9]+`). The literal value `dev` is FORBIDDEN as the default.

Mirror of test-install-sh-default-ref-not-dev.py but pinned at install.py — the
Python installer must NOT silently land plugin users on bleeding-edge dev.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
INSTALL_PY = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/install.py")

ALLOWED_PATTERNS = [
    r"^release/[0-9]+\.[0-9]+$",
    r"^v[0-9]+\.[0-9]+\.[0-9]+$",
]

# Pattern that locates the HARDCODED_STABLE_DEFAULT module constant:
#   HARDCODED_STABLE_DEFAULT = "release/1.3"
DEFAULT_RE = re.compile(r'HARDCODED_STABLE_DEFAULT\s*=\s*"([^"]+)"')

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-install-py-default-ref-not-dev.py")

# t1 — install.py exists on disk.
if os.path.isfile(INSTALL_PY):
    ok(1, f"install.py present at {INSTALL_PY}")
else:
    fail_t(1, f"install.py missing at {INSTALL_PY}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

source = open(INSTALL_PY).read()

# t2 — locate the HARDCODED_STABLE_DEFAULT constant.
m = DEFAULT_RE.search(source)
if m is None:
    fail_t(2, "could not locate HARDCODED_STABLE_DEFAULT in install.py")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)
default_value = m.group(1)
ok(2, f"located HARDCODED_STABLE_DEFAULT: {default_value!r}")

# t3 — default value is NOT exactly 'dev'.
if default_value == "dev":
    fail_t(3, "HARDCODED_STABLE_DEFAULT is literal 'dev' (FORBIDDEN per Inv 29)")
else:
    ok(3, f"HARDCODED_STABLE_DEFAULT is not 'dev': {default_value!r}")

# t4 — default value matches one of the allowed patterns.
if any(re.match(p, default_value) for p in ALLOWED_PATTERNS):
    ok(4, f"HARDCODED_STABLE_DEFAULT {default_value!r} matches an allowed stable channel pattern")
else:
    fail_t(4, f"HARDCODED_STABLE_DEFAULT {default_value!r} does not match release/X.Y or vX.Y.Z")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
