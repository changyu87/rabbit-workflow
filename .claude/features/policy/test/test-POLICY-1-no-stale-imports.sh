#!/usr/bin/env bash
# test-POLICY-1-no-stale-imports.sh — assert no stale @-imports in any CLAUDE.md.
# Verifies policy spec invariant 2: workflow-rules.md does not exist, so no
# CLAUDE.md may @-import it. Also verifies test-imports-resolve.sh uses a
# regex that matches the actual @.claude/... import format (not @./..).
#
# Version: 1.0.0
# Owner: rabbit-workflow team (policy)
# Deprecation criterion: when Claude Code enforces @-import resolution natively.
set -u

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}"
FEATURE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

PASS=0; FAIL=0
ok()  { echo "  ok   $*"; PASS=$((PASS+1)); }
ko()  { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: CLAUDE.md at repo root does NOT @-import workflow-rules.md
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
if [ -f "$CLAUDE_MD" ]; then
  if grep -qF '@.claude/features/policy/workflow-rules.md' "$CLAUDE_MD"; then
    ko "t1: CLAUDE.md @-imports workflow-rules.md (stale reference — file does not exist)"
  else
    ok "t1: CLAUDE.md does not @-import workflow-rules.md"
  fi
else
  ko "t1: CLAUDE.md not found at repo root"
fi

# t2: test-imports-resolve.sh must detect @-imports in CLAUDE.md (i.e. correct regex).
# The actual CLAUDE.md imports are '@.claude/...' format (no dot-slash between @ and path).
# If the regex '^@\./...' is used, 0 imports are found (regex bug).
IMPORTS_TEST="$FEATURE_DIR/test/test-imports-resolve.sh"
if [ -f "$IMPORTS_TEST" ]; then
  IMPORTS_OUTPUT="$(bash "$IMPORTS_TEST" 2>&1 || true)"
  IMPORTS_TOTAL="$(echo "$IMPORTS_OUTPUT" | grep -cE '^  (ok|FAIL)' 2>/dev/null || true)"
  if [ "${IMPORTS_TOTAL:-0}" -eq 0 ]; then
    ko "t2: test-imports-resolve.sh found 0 @-imports — regex does not match '@.claude/...' format"
  else
    ok "t2: test-imports-resolve.sh found ${IMPORTS_TOTAL} @-import(s) — regex works"
  fi
else
  ko "t2: test-imports-resolve.sh not found"
fi

echo ""
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
