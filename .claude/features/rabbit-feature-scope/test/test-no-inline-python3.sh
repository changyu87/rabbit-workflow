#!/bin/bash
# test-no-inline-python3.sh — assert resolve-scope.sh has no inline python3 calls.
# Part of CONTRACT-BACKLOG-5: unify tech stack to pure Python scripts.
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-feature-scope/scripts/resolve-scope.sh"
HELPER="$REPO_ROOT/.claude/features/rabbit-feature-scope/scripts/format-feature-context.py"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# 1. resolve-scope.sh must not contain inline 'python3 -c' calls
if grep -q "python3[[:space:]]*-c" "$SCRIPT" 2>/dev/null; then
  fail "resolve-scope.sh contains inline python3 -c call"
else
  ok "resolve-scope.sh has no inline python3 -c"
fi

# 2. resolve-scope.sh must not contain python3 heredocs (python3 <<)
if grep -q "python3[[:space:]]*<<" "$SCRIPT" 2>/dev/null; then
  fail "resolve-scope.sh contains python3 heredoc"
else
  ok "resolve-scope.sh has no python3 heredoc"
fi

# 3. format-feature-context.py must exist
[ -f "$HELPER" ] && ok "format-feature-context.py exists" || fail "format-feature-context.py not found"

# 4. format-feature-context.py must produce non-empty output for valid JSON input
if [ -f "$HELPER" ]; then
  sample='[{"name":"feat-a","path":".claude/features/feat-a","summary":"does A","tdd_state":"test-green"}]'
  out=$(echo "$sample" | python3 "$HELPER" 2>/dev/null)
  [ -n "$out" ] && ok "format-feature-context.py produces non-empty output" || fail "format-feature-context.py produced empty output"
else
  fail "format-feature-context.py skipped (file missing)"
fi

# 5. resolve-scope.sh invokes format-feature-context.py (not python3 -c)
if grep -q "format-feature-context.py" "$SCRIPT" 2>/dev/null; then
  ok "resolve-scope.sh invokes format-feature-context.py"
else
  fail "resolve-scope.sh does not invoke format-feature-context.py"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
