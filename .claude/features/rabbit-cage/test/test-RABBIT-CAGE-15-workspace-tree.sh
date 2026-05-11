#!/usr/bin/env bash
# test-RABBIT-CAGE-15-workspace-tree.sh
# Regression tests for stale annotations and broken is_bug_dir regex in workspace-tree.sh.
#
# Bug: RABBIT-CAGE-15 — workspace-tree.sh: stale annotations and broken is_bug_dir regex
#   after centralized storage refactor.
#
# Issues covered:
#   1. ANNOTATIONS still references "bugs_root" in feature.json description (stale field)
#   2. ANNOTATIONS missing entry for .claude/bugs/ (centralized bugs dir, no annotation)
#   3. ANNOTATIONS missing entry for .claude/backlogs/ (centralized backlogs dir, no annotation)
#   4. STRUCTURAL_DIRS missing "backlogs" (default-mode tree shows backlogs/ as unstructured)
#   5. STRUCTURAL_DIRS missing "rabbit-bug" (default-mode tree skips rabbit-bug feature dir)
#   6. is_bug_dir() regex ^[A-Z]+-[A-Z]+-\d+$ does NOT match RABBIT-CAGE-BACKLOG-1
#
# All 6 tests MUST FAIL against the current (unfixed) workspace-tree.sh.
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
WORKSPACE_TREE="$REPO_ROOT/.claude/features/rabbit-cage/scripts/workspace-tree.sh"

FAILURES=0

ok() {
    echo "  PASS t$1: $2"
}

fail_t() {
    echo "  FAIL t$1: $2"
    FAILURES=$(( FAILURES + 1 ))
}

echo "test-RABBIT-CAGE-15-workspace-tree.sh"
echo ""

# Capture --full output once for tests t1-t3
FULL_OUT="$(bash "$WORKSPACE_TREE" --full 2>/dev/null)"

# t1: --full output must NOT contain "bugs_root"
# ANNOTATIONS entry for feature.json still says "feature manifest: owner, tdd_state, surface, bugs_root"
# which is stale — bugs_root field was removed in the centralized storage refactor.
if echo "$FULL_OUT" | grep -q "bugs_root"; then
    fail_t 1 "workspace-tree.sh --full output still contains stale 'bugs_root' annotation (ANNOTATIONS[feature.json] not updated)"
else
    ok 1 "workspace-tree.sh --full output does not contain 'bugs_root'"
fi

# t2: --full output must contain ".claude/bugs" as annotation text
# After the refactor, bugs moved to .claude/bugs/ and ANNOTATIONS must annotate it.
# We look for the annotation text matching ".claude/bugs" appearing anywhere in the output.
if echo "$FULL_OUT" | grep -q '\.claude/bugs'; then
    ok 2 "workspace-tree.sh --full output contains '.claude/bugs' annotation text"
else
    fail_t 2 "workspace-tree.sh --full output does NOT contain '.claude/bugs' annotation text — centralized bugs dir not annotated in ANNOTATIONS"
fi

# t3: --full output must contain ".claude/backlogs" as annotation text
# After the refactor, backlogs moved to .claude/backlogs/ and ANNOTATIONS must annotate it.
if echo "$FULL_OUT" | grep -q '\.claude/backlogs'; then
    ok 3 "workspace-tree.sh --full output contains '.claude/backlogs' annotation text"
else
    fail_t 3 "workspace-tree.sh --full output does NOT contain '.claude/backlogs' annotation text — centralized backlogs dir not annotated in ANNOTATIONS"
fi

# t4: workspace-tree.sh source must declare "backlogs" inside STRUCTURAL_DIRS
# Without this entry the backlogs/ directory is excluded from default-mode structural view.
if grep -q '"backlogs"' "$WORKSPACE_TREE"; then
    ok 4 "STRUCTURAL_DIRS in workspace-tree.sh contains 'backlogs'"
else
    fail_t 4 "STRUCTURAL_DIRS in workspace-tree.sh does NOT contain 'backlogs'"
fi

# t5: workspace-tree.sh source must declare "rabbit-bug" inside STRUCTURAL_DIRS
# Without this entry the rabbit-bug feature directory is excluded from the default-mode tree.
if grep -q '"rabbit-bug"' "$WORKSPACE_TREE"; then
    ok 5 "STRUCTURAL_DIRS in workspace-tree.sh contains 'rabbit-bug'"
else
    fail_t 5 "STRUCTURAL_DIRS in workspace-tree.sh does NOT contain 'rabbit-bug'"
fi

# t6: is_bug_dir regex in workspace-tree.sh must match RABBIT-CAGE-BACKLOG-1
# Current regex: ^[A-Z]+-[A-Z]+-\d+$  — matches RABBIT-CAGE-15 but NOT RABBIT-CAGE-BACKLOG-1
# The regex must be updated to accept IDs with more than two uppercase segments before the number.
REGEX_RESULT="$(python3 - "$WORKSPACE_TREE" <<'PYEOF'
import sys, re

script_path = sys.argv[1]
with open(script_path) as f:
    src = f.read()

# Extract the pattern used in is_bug_dir (first re.match call in the function body)
m = re.search(r"re\.match\(r'([^']+)'", src)
if not m:
    print("no_pattern_found")
    sys.exit(0)

pattern = m.group(1)
test_name = "RABBIT-CAGE-BACKLOG-1"
if bool(re.match(pattern, test_name)):
    print("matches")
else:
    print("no_match")
PYEOF
)"

if [ "$REGEX_RESULT" = "matches" ]; then
    ok 6 "is_bug_dir regex in workspace-tree.sh matches RABBIT-CAGE-BACKLOG-1"
else
    fail_t 6 "is_bug_dir regex does NOT match RABBIT-CAGE-BACKLOG-1 (result: $REGEX_RESULT) — backlog item dirs not recognized as valid dir names"
fi

echo ""
echo "Results: $(( 6 - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
