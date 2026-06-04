#!/usr/bin/env python3
"""rabbit-cage regression — install.py HARDCODED_STABLE_DEFAULT MUST byte-equal install.sh's RABBIT_REF default.

Spec Inv 27: the hardcoded stable-release default in install.py and the
RABBIT_REF default in install.sh are a single source of truth — each
release-cut PR bumps both in lock-step. This test pins that lock-step so a
drift between the two is a hard test failure.
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
INSTALL_SH = os.path.join(REPO_ROOT, "install.sh")

PY_RE = re.compile(r'HARDCODED_STABLE_DEFAULT\s*=\s*"([^"]+)"')
SH_RE = re.compile(r'RABBIT_REF="\$\{RABBIT_REF:-([^}]+)\}"')

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


print("test-install-py-default-ref-matches-install-sh.py")

if not os.path.isfile(INSTALL_PY):
    fail_t(1, f"install.py missing at {INSTALL_PY}")
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)
if not os.path.isfile(INSTALL_SH):
    fail_t(1, f"install.sh missing at {INSTALL_SH}")
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)
ok(1, "both install.py and install.sh present")

py_src = open(INSTALL_PY).read()
sh_src = open(INSTALL_SH).read()

py_m = PY_RE.search(py_src)
sh_m = SH_RE.search(sh_src)

if py_m is None:
    fail_t(2, "could not locate HARDCODED_STABLE_DEFAULT in install.py")
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)
if sh_m is None:
    fail_t(2, "could not locate RABBIT_REF default in install.sh")
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)
ok(2, "located both defaults")

py_val = py_m.group(1)
sh_val = sh_m.group(1)

if py_val == sh_val:
    ok(3, f"install.py default {py_val!r} byte-equals install.sh default {sh_val!r}")
else:
    fail_t(3, f"DRIFT: install.py default {py_val!r} != install.sh default {sh_val!r} (Inv 27 lock-step)")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
