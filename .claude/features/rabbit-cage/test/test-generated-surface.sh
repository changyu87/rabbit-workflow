#!/usr/bin/env bash
# test-generated-surface.sh — drift oracle for workspace-generated artifacts.
#
# Reads build-contract.json. Verifies build.sh exists, then diffs each
# check_on_stop:true copy-file target against its source.
# Exits 0 (all pass) or 1 (any fail).
#
# Used by: sync-check.sh (Stop hook) + TDD test suite.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively manages workspace artifact generation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CONTRACT="$REPO_ROOT/.claude/features/contract/build-contract.json"
BUILD_SH="$REPO_ROOT/.claude/features/rabbit-cage/scripts/build.py"

pass=0
fail=0

ok()     { echo "  PASS t$1: $2"; pass=$((pass+1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail+1)); }

echo "test-generated-surface.sh"

# t1: build.sh exists and is executable
if [ -x "$BUILD_SH" ]; then
    ok 1 "build.sh exists and is executable"
else
    fail_t 1 "build.sh not found or not executable at $BUILD_SH"
fi

# t2: build-contract.json exists
if [ -f "$CONTRACT" ]; then
    ok 2 "build-contract.json exists"
else
    fail_t 2 "build-contract.json not found at $CONTRACT"
fi

if [ "$fail" -gt 0 ]; then
    echo ""
    echo "Results: $pass passed, $fail failed"
    exit 1
fi

# t3+: each check_on_stop:true copy-file target matches its source
t=3
while IFS=$'\t' read -r name source destination; do
    src_abs="$REPO_ROOT/$source"
    dst_abs="$REPO_ROOT/$destination"
    if [ ! -f "$dst_abs" ]; then
        fail_t $t "$name: destination missing ($destination)"
    elif diff -q "$src_abs" "$dst_abs" >/dev/null 2>&1; then
        ok $t "$name: matches source"
    else
        fail_t $t "$name: drifted from source"
    fi
    t=$((t+1))
done < <(python3 -c "
import json
with open('$CONTRACT') as f:
    c = json.load(f)
for t in c['targets']:
    if t.get('check_on_stop') and t['type'] == 'copy-file':
        print(t['name'] + '\t' + t['source'] + '\t' + t['destination'])
")

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
