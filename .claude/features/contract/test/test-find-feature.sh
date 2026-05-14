#!/bin/bash
# test-find-feature.sh — tests for distributed feature registry lookup
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
# find-feature.sh lives in the contract feature (cross-feature utility)
SCRIPT="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# Test 1: script exists and is executable
[ -x "$SCRIPT" ] && ok "script is executable" || fail "script not executable or missing"

# Test 2: find a known feature by name returns a path containing that name
result=$("$SCRIPT" contract 2>/dev/null)
echo "$result" | grep -q "features/contract" && ok "find contract returns correct path" || fail "find contract: got '$result'"

# Test 3: unknown feature exits 1
"$SCRIPT" no-such-feature 2>/dev/null; code=$?
[ "$code" -eq 1 ] && ok "unknown feature exits 1" || fail "unknown feature exit code: $code"

# Test 4: --list includes at least these core features (subset check — not exhaustive)
list=$("$SCRIPT" --list 2>/dev/null)
# Subset check — at minimum these core features must be present in --list output
for fname in contract policy rabbit-bug rabbit-backlog rabbit-cage tdd-state-machine; do
  echo "$list" | grep -q "^${fname}$" && ok "--list includes $fname" || fail "--list missing $fname"
done

# Test 5: --list-json is a valid JSON array
json=$("$SCRIPT" --list-json 2>/dev/null)
echo "$json" | python3 -c "import json,sys; a=json.load(sys.stdin); assert isinstance(a,list)" 2>/dev/null \
  && ok "--list-json is valid JSON array" || fail "--list-json not valid JSON"

# Test 6: --list-json entries have required fields (name, path, summary, tdd_state)
echo "$json" | python3 -c "
import json, sys
a = json.load(sys.stdin)
for e in a:
    for f in ('name','path','summary','tdd_state'):
        assert f in e, f'missing field {f} in {e}'
" 2>/dev/null && ok "--list-json entries have all required fields" || fail "--list-json entries missing fields"

# Test 7: returned path exists on disk (handles both absolute and relative paths)
path=$("$SCRIPT" contract 2>/dev/null)
if [ -d "$path" ] || [ -d "$REPO_ROOT/$path" ]; then
  ok "returned path exists on disk"
else
  fail "path not on disk: '$path'"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
