#!/usr/bin/env bash
# run.sh — Master test runner for the policy feature.
# Executes all test scripts in sequence. Exits non-zero on any failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_test() {
  local script="$1"
  echo "==> Running: $script"
  bash "$SCRIPT_DIR/$script"
  echo "    PASS: $script"
}

run_test "test-files-exist.sh"
run_test "test-workflow-rules-sections.sh"
run_test "test-rule-files-content.sh"
run_test "test-imports-resolve.sh"
run_test "test-backlog003.sh"
run_test "test-backlog006.sh"
run_test "test-policy-consolidation.sh"

echo ""
echo "All tests passed."
