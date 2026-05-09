#!/bin/bash
# test-files-exist.sh — verify that all required onboard feature files exist.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0; FAIL=0
ok()   { echo "  ok   $*"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

check_file() {
  local rel="$1"
  local path="$FEATURE_DIR/$rel"
  [ -f "$path" ] && ok "$rel exists" || ko "$rel missing"
}

check_exec() {
  local rel="$1"
  local path="$FEATURE_DIR/$rel"
  [ -x "$path" ] && ok "$rel is executable" || ko "$rel is not executable"
}

check_file "feature.json"
check_file "docs/spec/spec.md"
check_file "docs/spec/contract.md"
check_file "scripts/rabbit-project.sh"
check_exec "scripts/rabbit-project.sh"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
