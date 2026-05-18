#!/usr/bin/env python3
"""Regression tests for stale annotations and broken is_bug_dir regex in workspace-tree.py."""
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
WORKSPACE_TREE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/workspace-tree.py")

failures = 0


def ok(t, msg):
    print(f"  PASS t{t}: {msg}")


def fail_t(t, msg):
    global failures
    print(f"  FAIL t{t}: {msg}")
    failures += 1


print("test-RABBIT-CAGE-15-workspace-tree.py")
print()

result = subprocess.run([sys.executable, WORKSPACE_TREE, "--full"], capture_output=True, text=True)
full_out = result.stdout

# t1
if "bugs_root" in full_out:
    fail_t(1, "workspace-tree.py --full output still contains stale 'bugs_root' annotation (ANNOTATIONS[feature.json] not updated)")
else:
    ok(1, "workspace-tree.py --full output does not contain 'bugs_root'")

# t2
if ".claude/bugs" in full_out:
    ok(2, "workspace-tree.py --full output contains '.claude/bugs' annotation text")
else:
    fail_t(2, "workspace-tree.py --full output does NOT contain '.claude/bugs' annotation text — centralized bugs dir not annotated in ANNOTATIONS")

# t3
if ".claude/backlogs" in full_out:
    ok(3, "workspace-tree.py --full output contains '.claude/backlogs' annotation text")
else:
    fail_t(3, "workspace-tree.py --full output does NOT contain '.claude/backlogs' annotation text — centralized backlogs dir not annotated in ANNOTATIONS")

with open(WORKSPACE_TREE) as f:
    wt_src = f.read()

# t4
if '"backlogs"' in wt_src:
    ok(4, "STRUCTURAL_DIRS in workspace-tree.py contains 'backlogs'")
else:
    fail_t(4, "STRUCTURAL_DIRS in workspace-tree.py does NOT contain 'backlogs'")

# t5 (updated, BUG-46): rabbit-bug and rabbit-backlog features were
# consolidated into rabbit-file; STRUCTURAL_DIRS must reference the new
# feature name instead.
if '"rabbit-file"' in wt_src:
    ok(5, "STRUCTURAL_DIRS in workspace-tree.py contains 'rabbit-file' (post BUG-46 consolidation)")
else:
    fail_t(5, "STRUCTURAL_DIRS in workspace-tree.py does NOT contain 'rabbit-file' — annotations not updated for the consolidated feature")

# t6: regex check
m = re.search(r"re\.match\(r'([^']+)'", wt_src)
test_name = "RABBIT-CAGE-BACKLOG-1"
regex_result = "no_pattern_found"
if m:
    pattern = m.group(1)
    regex_result = "matches" if re.match(pattern, test_name) else "no_match"

if regex_result == "matches":
    ok(6, "is_bug_dir regex in workspace-tree.py matches RABBIT-CAGE-BACKLOG-1")
else:
    fail_t(6, f"is_bug_dir regex in workspace-tree.py does NOT match RABBIT-CAGE-BACKLOG-1 (result: {regex_result}) — backlog item dirs not recognized as valid dir names")

print()
print(f"Results: {6 - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
