#!/bin/bash
# step-8-final.sh — Integration test for Step 8.
# Verifies: post-transition hook in tdd-step.sh, onboard feature, registry, command stub.
# Non-interactive, exits 0 on full pass.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0
ok()   { echo "  ok   $*"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

echo "=== step-8-final integration test ==="
echo

# 1. tdd-step.sh contains rebuild-registry hook
echo "-- Check 1: tdd-step.sh contains test-green hook referencing rebuild-registry"
TDD_STEP="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-step.sh"
if grep -q "rebuild-registry" "$TDD_STEP"; then
  ok "tdd-step.sh references rebuild-registry.sh"
else
  ko "tdd-step.sh does NOT reference rebuild-registry.sh"
fi
if grep -q "test-green" "$TDD_STEP"; then
  ok "tdd-step.sh references test-green state in hook"
else
  ko "tdd-step.sh missing test-green hook check"
fi

# 2. onboard feature directory exists and feature.json is valid JSON
echo "-- Check 2: onboard feature.json exists and is valid JSON"
ONBOARD_JSON="$REPO_ROOT/.claude/features/onboard/feature.json"
if [ -f "$ONBOARD_JSON" ]; then
  if python3 -c "import json; json.load(open('$ONBOARD_JSON'))" 2>/dev/null; then
    ok "onboard/feature.json exists and is valid JSON"
  else
    ko "onboard/feature.json is not valid JSON"
  fi
else
  ko "onboard/feature.json does not exist"
fi

# 3. rabbit-project.sh is executable
echo "-- Check 3: onboard/scripts/rabbit-project.sh is executable"
RABBIT_PROJECT="$REPO_ROOT/.claude/features/onboard/scripts/rabbit-project.sh"
if [ -x "$RABBIT_PROJECT" ]; then
  ok "rabbit-project.sh is executable"
else
  ko "rabbit-project.sh is not executable"
fi

# 4. registry.json contains "onboard"
echo "-- Check 4: registry.json contains onboard entry"
REGISTRY="$REPO_ROOT/.claude/features/registry.json"
if python3 -c "import json; d=json.load(open('$REGISTRY')); assert 'onboard' in d.get('features',{})" 2>/dev/null; then
  ok "registry.json contains onboard"
else
  ko "registry.json does NOT contain onboard"
fi

# 5. /rabbit-project command stub exists
echo "-- Check 5: .claude/commands/rabbit-project.md exists"
COMMAND_STUB="$REPO_ROOT/.claude/commands/rabbit-project.md"
if [ -f "$COMMAND_STUB" ]; then
  ok ".claude/commands/rabbit-project.md exists"
else
  ko ".claude/commands/rabbit-project.md does not exist"
fi

# 6. Run onboard test suite
echo "-- Check 6: onboard/test/run.sh exits 0"
ONBOARD_RUN="$REPO_ROOT/.claude/features/onboard/test/run.sh"
if bash "$ONBOARD_RUN" >/dev/null 2>&1; then
  ok "onboard/test/run.sh passes"
else
  echo "    (re-running with output for diagnostics)"
  bash "$ONBOARD_RUN"
  ko "onboard/test/run.sh FAILED"
fi

echo
echo "=== summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
