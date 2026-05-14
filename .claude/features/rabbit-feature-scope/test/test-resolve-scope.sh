#!/bin/bash
# test-resolve-scope.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-feature-scope/scripts/resolve-scope.sh"
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# 1. script exists and is executable
[ -x "$SCRIPT" ] && ok "script executable" || fail "not executable or missing"

# 2. exits 2 with no args
"$SCRIPT" 2>/dev/null; code=$?
[ "$code" -eq 2 ] && ok "exits 2 with no args" || fail "exit code no-args: $code"

# 3. emits non-empty prompt for a request
prompt=$("$SCRIPT" "fix the scope guard bug" 2>/dev/null)
[ -n "$prompt" ] && ok "emits non-empty prompt" || fail "empty prompt"

# 4. prompt includes at least one feature name from find-feature.sh --list
first=$(bash "$FIND_FEATURE" --list 2>/dev/null | head -1)
echo "$prompt" | grep -q "$first" && ok "prompt includes feature name '$first'" || fail "prompt missing feature '$first'"

# 5. prompt includes the request text verbatim
echo "$prompt" | grep -q "fix the scope guard bug" && ok "prompt includes request text" || fail "prompt missing request text"

# 6. prompt specifies the JSON response schema
echo "$prompt" | grep -q '"features"' && ok "prompt specifies JSON schema" || fail "prompt missing JSON schema"

# 7. prompt instructs single-line JSON output
echo "$prompt" | grep -q "single line" && ok "prompt says single-line JSON" || fail "prompt missing single-line instruction"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
