#!/usr/bin/env python3
"""rabbit-cage regression — install.sh offline-fallback ref MUST be a stable channel.

Bug #279 / spec Inv 26 (amended #307, #848): #848 made install.sh's DEFAULT path
resolve the latest published release DYNAMICALLY (GitHub releases/latest). The
hardcoded `RABBIT_FALLBACK_REF` is now an OFFLINE FALLBACK only — used when the
dynamic latest-lookup fails. The fallback literal MUST match ONE of the allowed
stable-channel patterns: 3-field `release/[0-9]+\\.[0-9]+\\.[0-9]+`, legacy
2-field `release/[0-9]+\\.[0-9]+`, or a semver tag (`v[0-9]+\\.[0-9]+\\.[0-9]+`).
The literal value `dev` is FORBIDDEN as the fallback.

A failed latest-lookup MUST never silently land plugin users on bleeding-edge
dev — this test is the load-bearing safety against re-pointing the fallback at
dev during a refactor.
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
INSTALL_SH = os.path.join(REPO_ROOT, "install.sh")

ALLOWED_PATTERNS = [
    r"^release/[0-9]+\.[0-9]+(\.[0-9]+)?$",
    r"^v[0-9]+\.[0-9]+\.[0-9]+$",
]

# Pattern that locates the RABBIT_FALLBACK_REF declaration:
#   RABBIT_FALLBACK_REF="v9.0.0"
FALLBACK_RE = re.compile(r'RABBIT_FALLBACK_REF="([^"]+)"')

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


print("test-install-sh-default-ref-not-dev.py")

# t1 — install.sh exists on disk.
if os.path.isfile(INSTALL_SH):
    ok(1, f"install.sh present at {INSTALL_SH}")
else:
    fail_t(1, f"install.sh missing at {INSTALL_SH}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

source = open(INSTALL_SH).read()

# t2 — locate the RABBIT_FALLBACK_REF declaration.
m = FALLBACK_RE.search(source)
if m is None:
    fail_t(2, "could not locate RABBIT_FALLBACK_REF declaration in install.sh")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)
fallback_value = m.group(1)
ok(2, f"located RABBIT_FALLBACK_REF declaration: {fallback_value!r}")

# t3 — fallback value is NOT exactly 'dev'.
if fallback_value == "dev":
    fail_t(3, "RABBIT_FALLBACK_REF is the literal 'dev' (FORBIDDEN per Inv 26)")
else:
    ok(3, f"RABBIT_FALLBACK_REF is not 'dev': {fallback_value!r}")

# t4 — fallback value matches one of the allowed patterns.
if any(re.match(p, fallback_value) for p in ALLOWED_PATTERNS):
    ok(4, f"RABBIT_FALLBACK_REF {fallback_value!r} matches an allowed stable channel pattern")
else:
    fail_t(4, f"RABBIT_FALLBACK_REF {fallback_value!r} does not match release/X.Y[.Z] or vX.Y.Z")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
