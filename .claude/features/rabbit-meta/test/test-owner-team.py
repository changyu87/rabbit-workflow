#!/usr/bin/env python3
"""test-owner-team.py — owner sweep (issue #416)

End-to-end test verifying no owner-bearing location in rabbit-meta names an
individual; every owner field/docstring reads "rabbit-workflow team":
  - t1: feature.json "owner" == "rabbit-workflow team"
  - t2: spec.md frontmatter owner: rabbit-workflow team (resolved via the
        contract resolver, flat docs/ layout preferred)
  - t3: every lib/*.py module docstring "Owner:" line reads the team
  - t4: no "cyxu" owner string remains anywhere in the feature tree
"""

import importlib.util
import os
import re
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FEATURES_ROOT = os.path.dirname(FEATURE_DIR)
CHECKS_PATH = os.path.join(FEATURES_ROOT, "contract", "lib", "checks.py")
_spec = importlib.util.spec_from_file_location("checks", CHECKS_PATH)
_checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checks)

TEAM = "rabbit-workflow team"

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS {n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL {n}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: feature.json owner
with open(os.path.join(FEATURE_DIR, "feature.json")) as f:
    fj = json.load(f)
if fj.get("owner") == TEAM:
    ok("t1", f"feature.json owner == {TEAM!r}")
else:
    fail_t("t1", f"feature.json owner is {fj.get('owner')!r}, expected {TEAM!r}")

# t2: spec.md frontmatter owner (resolved, flat docs/ layout preferred)
with open(_checks.resolve_spec_path(FEATURE_DIR, "spec.md")) as f:
    spec = f.read()
m = re.search(r"^owner:\s*(.+)$", spec, re.MULTILINE)
if m and m.group(1).strip() == TEAM:
    ok("t2", f"spec.md owner == {TEAM!r}")
else:
    got = m.group(1).strip() if m else "<missing>"
    fail_t("t2", f"spec.md owner is {got!r}, expected {TEAM!r}")

# t3: every lib/*.py module docstring "Owner:" line reads the team
lib_dir = os.path.join(FEATURE_DIR, "lib")
bad_docstrings = []
for fn in sorted(os.listdir(lib_dir)):
    if not fn.endswith(".py"):
        continue
    with open(os.path.join(lib_dir, fn)) as f:
        body = f.read()
    for line in body.splitlines():
        mo = re.match(r"^Owner:\s*(.+)$", line.strip())
        if mo and mo.group(1).strip() != TEAM:
            bad_docstrings.append(f"{fn}: {mo.group(1).strip()!r}")
if not bad_docstrings:
    ok("t3", "all lib/*.py Owner: docstrings read the team")
else:
    fail_t("t3", f"non-team Owner: docstrings: {bad_docstrings}")

# t4: no individual-owner "cyxu" string remains in the feature tree
offenders = []
for root, dirs, files in os.walk(FEATURE_DIR):
    if "__pycache__" in root:
        continue
    for fn in files:
        if fn == os.path.basename(__file__):
            continue
        path = os.path.join(root, fn)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        if "cyxu" in content:
            offenders.append(os.path.relpath(path, FEATURE_DIR))
if not offenders:
    ok("t4", "no 'cyxu' owner string remains in feature tree")
else:
    fail_t("t4", f"'cyxu' still present in: {offenders}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
