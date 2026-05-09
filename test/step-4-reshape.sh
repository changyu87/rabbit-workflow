#!/usr/bin/env bash
# test/step-4-reshape.sh — verify Step 4 reshape of feature dirs and registry.json.
#
# Exit 0 = all checks pass.
# Exit 1 = one or more checks failed.

set -u

FEATURES_DIR="/home/cyxu/workflow-dev/rabbit-run/.claude/features"
PASS=0
FAIL=0

check() {
  local desc="$1"
  local result="$2"   # "ok" or "fail"
  if [ "$result" = "ok" ]; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"
    FAIL=$((FAIL + 1))
  fi
}

file_exists()   { [ -f "$1" ] && echo "ok" || echo "fail"; }
file_absent()   { [ ! -f "$1" ] && echo "ok" || echo "fail"; }
dir_exists()    { [ -d "$1" ] && echo "ok" || echo "fail"; }

echo "=== Step 4 Reshape Test ==="
echo ""

# 1. Verify the 11 reshaped features have the new structure
RESHAPED="auto-refresh bug-filing feature-scaffolder feature-skeleton hard-rules install-distribute naming-convention policy-enforcement root-management scope-guard tdd-state-machine"

echo "--- Checking reshaped feature structure ---"
for feat in $RESHAPED; do
  feat_dir="$FEATURES_DIR/$feat"
  check "$feat: docs/spec/spec.md exists"      "$(file_exists "$feat_dir/docs/spec/spec.md")"
  check "$feat: docs/spec/contract.md exists"  "$(file_exists "$feat_dir/docs/spec/contract.md")"
  check "$feat: docs/bugs/.gitkeep exists"     "$(file_exists "$feat_dir/docs/bugs/.gitkeep")"
  check "$feat: spec.md at root is gone"       "$(file_absent "$feat_dir/spec.md")"
  check "$feat: contract.md at root is gone"   "$(file_absent "$feat_dir/contract.md")"
done

echo ""
echo "--- Checking policy/ and contract/ are untouched ---"
check "policy: docs/spec/spec.md exists"     "$(file_exists "$FEATURES_DIR/policy/docs/spec/spec.md")"
check "contract: docs/spec/spec.md exists"   "$(file_exists "$FEATURES_DIR/contract/docs/spec/spec.md")"

echo ""
echo "--- Checking registry.json ---"
REGISTRY="$FEATURES_DIR/registry.json"
check "registry.json exists" "$(file_exists "$REGISTRY")"

if [ -f "$REGISTRY" ]; then
  if python3 -m json.tool "$REGISTRY" >/dev/null 2>&1; then
    check "registry.json is valid JSON" "ok"
  else
    check "registry.json is valid JSON" "fail"
  fi

  # Count features
  FEAT_COUNT=$(python3 -c "
import json, sys
with open('$REGISTRY') as f:
    r = json.load(f)
print(len(r.get('features', {})))
" 2>/dev/null)

  if [ "$FEAT_COUNT" = "13" ]; then
    check "registry.json contains 13 features (got: $FEAT_COUNT)" "ok"
  else
    check "registry.json contains 13 features (got: $FEAT_COUNT)" "fail"
  fi

  # Check all 13 expected features are present
  EXPECTED="auto-refresh bug-filing contract feature-scaffolder feature-skeleton hard-rules install-distribute naming-convention policy policy-enforcement root-management scope-guard tdd-state-machine"
  for feat in $EXPECTED; do
    PRESENT=$(python3 -c "
import json
with open('$REGISTRY') as f:
    r = json.load(f)
print('ok' if '$feat' in r.get('features', {}) else 'fail')
" 2>/dev/null)
    check "registry.json has entry: $feat" "$PRESENT"
  done
fi

echo ""
echo "--- Checking no maps.json under .claude/ ---"
MAPS_COUNT=$(find /home/cyxu/workflow-dev/rabbit-run/.claude -name "maps.json" -not -path "*/archive/*" 2>/dev/null | wc -l)
if [ "$MAPS_COUNT" -eq 0 ]; then
  check "no maps.json files found under .claude/" "ok"
else
  check "no maps.json files found under .claude/ (found: $MAPS_COUNT)" "fail"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
