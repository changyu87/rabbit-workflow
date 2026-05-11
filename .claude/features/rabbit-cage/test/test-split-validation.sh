#!/usr/bin/env bash
# rabbit-cage split-validation tests
# Verifies that bug/backlog scripts and data have been removed from rabbit-cage
# after the split to standalone rabbit-bug and rabbit-backlog features.
# These tests MUST FAIL until the split is implemented.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CAGE_DIR="$REPO_ROOT/.claude/features/rabbit-cage"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

echo "test-split-validation.sh"

# t1: file-bug.sh does NOT exist under rabbit-cage/scripts/
if [ ! -f "$CAGE_DIR/scripts/file-bug.sh" ]; then
    ok 1 "file-bug.sh does not exist in rabbit-cage/scripts/"
else
    fail_t 1 "file-bug.sh still exists in rabbit-cage/scripts/ — should be in rabbit-bug"
fi

# t2: bug-status.sh does NOT exist under rabbit-cage/scripts/
if [ ! -f "$CAGE_DIR/scripts/bug-status.sh" ]; then
    ok 2 "bug-status.sh does not exist in rabbit-cage/scripts/"
else
    fail_t 2 "bug-status.sh still exists in rabbit-cage/scripts/ — should be in rabbit-bug"
fi

# t3: list-bugs.sh does NOT exist under rabbit-cage/scripts/
if [ ! -f "$CAGE_DIR/scripts/list-bugs.sh" ]; then
    ok 3 "list-bugs.sh does not exist in rabbit-cage/scripts/"
else
    fail_t 3 "list-bugs.sh still exists in rabbit-cage/scripts/ — should be in rabbit-bug"
fi

# t4: file-backlog-item.sh does NOT exist under rabbit-cage/scripts/
if [ ! -f "$CAGE_DIR/scripts/file-backlog-item.sh" ]; then
    ok 4 "file-backlog-item.sh does not exist in rabbit-cage/scripts/"
else
    fail_t 4 "file-backlog-item.sh still exists in rabbit-cage/scripts/ — should be in rabbit-backlog"
fi

# t5: backlog-item-status.sh does NOT exist under rabbit-cage/scripts/
if [ ! -f "$CAGE_DIR/scripts/backlog-item-status.sh" ]; then
    ok 5 "backlog-item-status.sh does not exist in rabbit-cage/scripts/"
else
    fail_t 5 "backlog-item-status.sh still exists in rabbit-cage/scripts/ — should be in rabbit-backlog"
fi

# t6: rabbit-cage/feature.json does NOT have a bugs_root key
if python3 -c "import json,sys; d=json.load(open('$CAGE_DIR/feature.json')); sys.exit(0 if 'bugs_root' not in d else 1)" 2>/dev/null; then
    ok 6 "feature.json does not have a bugs_root key"
else
    fail_t 6 "feature.json still has a bugs_root key — must be removed after split"
fi

# t7: rabbit-cage/docs/bugs/ directory does NOT exist
if [ ! -d "$CAGE_DIR/docs/bugs" ]; then
    ok 7 "docs/bugs/ directory does not exist in rabbit-cage"
else
    fail_t 7 "docs/bugs/ still exists in rabbit-cage — should be moved to rabbit-bug"
fi

# t8: rabbit-cage/docs/backlog/ directory does NOT exist
if [ ! -d "$CAGE_DIR/docs/backlog" ]; then
    ok 8 "docs/backlog/ directory does not exist in rabbit-cage"
else
    fail_t 8 "docs/backlog/ still exists in rabbit-cage — should be moved to rabbit-backlog"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
