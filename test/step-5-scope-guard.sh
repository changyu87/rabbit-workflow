#!/bin/bash
# Integration test: Step 5 — scope-guard v2 + R8/R9.
# Non-interactive. All assertions are file-content checks.
set -u

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null)}"
SCOPE_GUARD="$REPO_ROOT/.claude/hooks/scope-guard.sh"
SCOPE_GUARD_FJ="$REPO_ROOT/.claude/features/scope-guard/feature.json"
HARD_RULES_SPEC="$REPO_ROOT/.claude/features/hard-rules/docs/spec/spec.md"
HARD_RULES_FJ="$REPO_ROOT/.claude/features/hard-rules/feature.json"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# 1. scope-guard.sh contains "v2.0.0"
grep -q "v2.0.0" "$SCOPE_GUARD" \
  && ok "scope-guard.sh header contains v2.0.0" \
  || ko "scope-guard.sh header missing v2.0.0"

# 2. Allowlist: scope-guard.sh references settings.json and settings.local.json
grep -q "settings\.json" "$SCOPE_GUARD" \
  && ok "scope-guard.sh references settings.json" \
  || ko "scope-guard.sh missing settings.json"

grep -q "settings\.local\.json" "$SCOPE_GUARD" \
  && ok "scope-guard.sh references settings.local.json" \
  || ko "scope-guard.sh missing settings.local.json"

# 3. Repo-root logic: scope-guard.sh uses REPO_ROOT and git
grep -q "REPO_ROOT" "$SCOPE_GUARD" \
  && ok "scope-guard.sh contains REPO_ROOT" \
  || ko "scope-guard.sh missing REPO_ROOT"

grep -q "git" "$SCOPE_GUARD" \
  && ok "scope-guard.sh contains git (for repo root detection)" \
  || ko "scope-guard.sh missing git"

# 4. hard-rules spec contains R8 and R9
grep -q "R8" "$HARD_RULES_SPEC" \
  && ok "hard-rules spec contains R8" \
  || ko "hard-rules spec missing R8"

grep -q "R9" "$HARD_RULES_SPEC" \
  && ok "hard-rules spec contains R9" \
  || ko "hard-rules spec missing R9"

# 5. scope-guard/feature.json version is 2.0.0
grep -q '"version": "2.0.0"' "$SCOPE_GUARD_FJ" \
  && ok "scope-guard/feature.json version is 2.0.0" \
  || ko "scope-guard/feature.json version is not 2.0.0"

# 6. hard-rules/feature.json version is 1.1.0
grep -q '"version": "1.1.0"' "$HARD_RULES_FJ" \
  && ok "hard-rules/feature.json version is 1.1.0" \
  || ko "hard-rules/feature.json version is not 1.1.0"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
