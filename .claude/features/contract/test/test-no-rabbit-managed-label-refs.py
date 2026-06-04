#!/usr/bin/env python3
"""test-no-rabbit-managed-label-refs.py — issue #760 (step 3 of #753).

End-to-end regression guard that the `rabbit-managed` LABEL — fully retired
once queue selection became actionability-based (#758) — leaves no stale
reference on contract's live surfaces.

Two checks:

  t1  workspace-structure.json's `rabbit-auto-evolve` node description no
      longer claims rabbit-managed-based selection; it MUST describe
      actionability-based selection (valid `feature:` + `priority:` labels).
  t2  No contract live surface (data files, schemas, scripts, doc surfaces,
      and tests' own logic) carries a stale `rabbit-managed` LABEL reference.
      Historical CHANGELOG entries are intentionally exempt — designed
      deprecation keeps the tombstone record. This test file is also exempt
      from its own scan (it names the retired token to describe what it bans).

Non-interactive. Exits non-zero on any failure.
"""

import json
import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
WS_STRUCTURE = os.path.join(FEATURE_DIR, "workspace-structure.json")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# --- t1: workspace-structure.json rabbit-auto-evolve node -----------------
with open(WS_STRUCTURE, encoding="utf-8") as f:
    ws = json.load(f)


def find_node(nodes, name):
    for n in nodes:
        if n.get("name") == name:
            return n
        child = find_node(n.get("children", []), name)
        if child:
            return child
    return None


rae = find_node(ws.get("nodes", []), "rabbit-auto-evolve")
if rae is None:
    ko("t1", "rabbit-auto-evolve node not found in workspace-structure.json")
else:
    desc = rae.get("description", "")
    if "rabbit-managed" in desc:
        ko("t1", f"rabbit-auto-evolve node still claims rabbit-managed: {desc}")
    elif "actionable" not in desc:
        ko("t1", f"rabbit-auto-evolve node does not describe actionable "
                 f"selection: {desc}")
    else:
        ok("t1", "rabbit-auto-evolve node describes actionability-based "
                 "selection, no rabbit-managed claim")


# --- t2: no stale rabbit-managed LABEL reference on live surfaces ---------
# Scan contract source/data/doc surfaces. Skip the CHANGELOG (historical
# tombstone record stays) and this test file itself (it names the token to
# ban it).
SELF = os.path.basename(__file__)
SKIP_REL = {
    os.path.join("docs", "CHANGELOG.md"),
}
SKIP_BASENAMES = {SELF}
SKIP_DIRS = {"__pycache__"}
SCAN_EXTS = {".json", ".py", ".md"}

# Match the bare `rabbit-managed` token, but not when it is part of this
# test's own filename fragment (`rabbit-managed-label-refs`), which appears
# in run.py's registration line and is not a label reference.
_RM_RE = re.compile(r"rabbit-managed(?!-label-refs)", re.IGNORECASE)

violations = []
for dirpath, dirnames, filenames in os.walk(FEATURE_DIR):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fn in filenames:
        if fn in SKIP_BASENAMES:
            continue
        ext = os.path.splitext(fn)[1]
        if ext not in SCAN_EXTS:
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, FEATURE_DIR)
        if rel in SKIP_REL:
            continue
        with open(full, encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                if _RM_RE.search(line):
                    violations.append((rel, lineno, line.rstrip()))

if violations:
    for rel, lineno, content in violations:
        ko("t2", f"{rel}:{lineno}: stale rabbit-managed reference: {content}")
else:
    ok("t2", "no stale rabbit-managed LABEL reference on contract surfaces")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    print("test-no-rabbit-managed-label-refs: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-no-rabbit-managed-label-refs: all checks passed.")
sys.exit(0)
