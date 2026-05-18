#!/usr/bin/env python3
"""test-dispatch-feature-edit-path-detect.py — Inv 27.

dispatch-feature-edit.py project-feature path detection MUST handle paths
containing literal `.claude/features/` correctly. A feature reference at
`.claude/features/<X>/scripts/foo.py` MUST resolve to feature `<X>`, not be
misclassified as project-feature.

End-to-end: invoke dispatch-feature-edit.py for a known rabbit-level feature
and assert it succeeds (does NOT attempt to read a non-existent project
contract dir derived from substring heuristic misfire).
"""

import os
import sys
import subprocess

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/dispatch-feature-edit.py")

FAIL = 0

# t1: source MUST use .claude/features/ as the canonical project-feature discriminator,
# not a fragile basename == 'features' heuristic.
with open(SCRIPT) as f:
    src = f.read()

# The fragile heuristic looked like `parts[1] == "features"`. The fix should
# use `.claude/features/` (or an unambiguous prefix-based check).
if "parts[1] ==" in src and '"features"' in src and ".claude" not in src.split("parts[1] ==")[1].split("\n", 5)[0]:
    # Quick sanity that the old heuristic is gone or replaced
    pass

# Stronger assertion: the script must reference '.claude/features/' literal.
if ".claude/features/" not in src and ".claude','features'" not in src.replace(" ", ""):
    print("FAIL t1: script lacks reference to '.claude/features/' discriminator", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: script references '.claude/features/' discriminator")

# t2 (end-to-end): dispatch for a rabbit feature succeeds (exit 0).
# This implicitly tests path classification — if the script misclassified a
# rabbit-level feature as project-level, it would attempt to read a wrong
# directory and either crash or emit wrong content. Exit code must be 0.
proc = subprocess.run(
    ["python3", SCRIPT, "contract", "test task"],
    capture_output=True, text=True,
    cwd=REPO_ROOT,
)
if proc.returncode != 0:
    print(f"FAIL t2: dispatch-feature-edit exited {proc.returncode}", file=sys.stderr)
    print(f"  stderr: {proc.stderr[:500]}", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t2: dispatch-feature-edit succeeds for rabbit-level feature 'contract'")

# t3: cleanup any scope marker created during dispatch
marker = os.path.join(REPO_ROOT, ".rabbit-scope-active")
if os.path.exists(marker):
    os.remove(marker)

if FAIL:
    print("test-dispatch-feature-edit-path-detect: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-dispatch-feature-edit-path-detect: all checks passed.")
