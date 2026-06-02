#!/usr/bin/env python3
"""rabbit-cage regression — install.sh default RABBIT_REF MUST be a stable channel.

Bug #279 / spec Inv 24 (amended #307): the default value of RABBIT_REF declared
in install.sh MUST match a stable release branch — either 3-field
`release/[0-9]+\\.[0-9]+\\.[0-9]+` (preferred, post-#307) or legacy 2-field
`release/[0-9]+\\.[0-9]+` (retained for backwards compat with release/1.0-1.10)
— or a semver tag (`v[0-9]+\\.[0-9]+\\.[0-9]+`). The literal value `dev` is
FORBIDDEN as the default.

Plugin users running the documented one-liner without an explicit RABBIT_REF
override MUST land on a stable, semver-tagged channel — never the bleeding-edge
dev branch. Developers who want dev can opt-in via `RABBIT_REF=dev curl ... | bash`.

Cutting a new release (e.g. release/1.1) MUST bump install.sh's default in the
same PR — this test is the load-bearing safety against accidentally re-pointing
the default at dev during a refactor.
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

# Pattern that locates the RABBIT_REF default declaration:
#   RABBIT_REF="${RABBIT_REF:-<value>}"
DEFAULT_RE = re.compile(r'RABBIT_REF="\$\{RABBIT_REF:-([^}]+)\}"')

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

# t2 — locate the RABBIT_REF default declaration.
m = DEFAULT_RE.search(source)
if m is None:
    fail_t(2, "could not locate RABBIT_REF default declaration in install.sh")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)
default_value = m.group(1)
ok(2, f"located RABBIT_REF default declaration: {default_value!r}")

# t3 — default value is NOT exactly 'dev'.
if default_value == "dev":
    fail_t(3, "RABBIT_REF default is the literal 'dev' (FORBIDDEN per Inv 24)")
else:
    ok(3, f"RABBIT_REF default is not 'dev': {default_value!r}")

# t4 — default value matches one of the allowed patterns.
if any(re.match(p, default_value) for p in ALLOWED_PATTERNS):
    ok(4, f"RABBIT_REF default {default_value!r} matches an allowed stable channel pattern")
else:
    fail_t(4, f"RABBIT_REF default {default_value!r} does not match release/X.Y[.Z] or vX.Y.Z")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
