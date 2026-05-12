#!/bin/bash
# Test: surface.skills in tdd-state-machine/feature.json must be []
# Invariant 9: skills are managed via build-contract.json copy-file entries;
# the surface.skills field is retired and must be an empty array.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
FEATURE_JSON="$REPO_ROOT/.claude/features/tdd-state-machine/feature.json"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: feature.json exists
t1() {
  if [ -f "$FEATURE_JSON" ]; then
    ok "t1: feature.json exists"
  else
    ko "t1: feature.json not found at $FEATURE_JSON"
  fi
}

# t2: surface.skills is exactly []
t2() {
  if ! [ -f "$FEATURE_JSON" ]; then
    ko "t2: feature.json not found — cannot check surface.skills"
    return
  fi
  local skills
  skills=$(jq -c '.surface.skills // []' "$FEATURE_JSON" 2>/dev/null)
  if [ "$skills" = "[]" ]; then
    ok "t2: surface.skills is [] (retired)"
  else
    ko "t2: surface.skills is not [] — got: $skills (must be empty; skills managed via build-contract.json)"
  fi
}

echo "running surface.skills retirement tests (tdd-state-machine)"
t1; t2
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
