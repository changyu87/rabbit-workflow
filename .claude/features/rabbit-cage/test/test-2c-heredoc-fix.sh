#!/usr/bin/env bash
# test-2c-heredoc-fix.sh
# Verifies that the single-quoted heredoc bug in test-2c-backlog-scaffolding.sh
# is fixed: <<'PYEOF' must not appear (bash won't expand ${CONTRACT} with it).
# R3-compliant: no interactive constructs, prints PASS/FAIL per assertion, exits 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
TARGET="${REPO_ROOT}/.claude/features/rabbit-cage/test/test-2c-backlog-scaffolding.sh"

FAILURES=0

assert() {
  local label="$1"
  local result="$2"
  if [ "$result" = "0" ]; then
    echo "PASS: ${label}"
  else
    echo "FAIL: ${label}"
    FAILURES=$(( FAILURES + 1 ))
  fi
}

# 1. The single-quoted heredoc <<'PYEOF' must NOT appear in test-2c-backlog-scaffolding.sh.
#    If it does appear, bash will not expand ${CONTRACT} before passing the path to Python.
grep -qF "<<'PYEOF'" "${TARGET}" 2>/dev/null
BAD_PATTERN_FOUND="$?"
# We want the pattern to be ABSENT, so exit 0 only when grep found nothing (exit 1)
[ "${BAD_PATTERN_FOUND}" -ne 0 ]
assert "test-2c-backlog-scaffolding.sh does NOT contain <<'PYEOF' (single-quoted heredoc)" "$?"

# Final result
echo ""
if [ "${FAILURES}" -eq 0 ]; then
  echo "ALL TESTS PASSED"
  exit 0
else
  echo "${FAILURES} TEST(S) FAILED"
  exit 1
fi
