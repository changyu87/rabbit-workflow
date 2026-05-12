#!/bin/bash
# run.sh — test runner for rabbit-backlog feature.
# Runs all test suites and aggregates results.

set -euo pipefail

TEST_DIR="$(cd "$(dirname "$0")" && pwd)"

pass=0
fail=0
errors=()

run_suite() {
  local script="$1"
  local name
  name="$(basename "$script")"
  echo "--- $name ---"
  if bash "$script"; then
    echo "  suite PASSED: $name"
  else
    echo "  suite FAILED: $name"
    errors+=("$name")
    fail=$((fail + 1))
  fi
  echo ""
}

echo "=== rabbit-backlog test runner ==="
echo ""

run_suite "$TEST_DIR/test-backlog-scripts.sh"
run_suite "$TEST_DIR/test-backlog-skill.sh"
run_suite "$TEST_DIR/test-backlog-state-machine.sh"
run_suite "$TEST_DIR/test-workspace-map-invocation.sh"
run_suite "$TEST_DIR/test-list-backlog.sh"

echo "=== Summary ==="
if [ "${#errors[@]}" -gt 0 ]; then
  echo "Failed suites:"
  for e in "${errors[@]}"; do
    echo "  - $e"
  done
  exit 1
fi
echo "All suites passed."
exit 0
