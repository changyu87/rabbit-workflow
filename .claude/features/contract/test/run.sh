#!/bin/bash
# run.sh — run all contract feature tests in sequence.
#
# Non-interactive. Exits non-zero on first failure.

set -eu

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_test() {
  local script="$1"
  echo "=== $script ==="
  bash "$TEST_DIR/$script"
  echo "--- PASS: $script ---"
  echo ""
}

run_test "test-files-exist.sh"
run_test "test-policy-block.sh"
run_test "test-templates-have-version.sh"
run_test "test-schemas-valid-json.sh"
run_test "test-rabbit-triage.sh"

echo "ALL TESTS PASSED"
