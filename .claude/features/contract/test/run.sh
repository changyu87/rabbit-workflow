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
run_test "test-dispatch.sh"
run_test "test-validate-no-bugs-root.sh"
run_test "test-audit-orphan-storage.sh"
run_test "test-relink-no-skills.sh"
run_test "test-dispatch-spec-update.sh"
run_test "test-skill-command-templates.sh"
run_test "test-rabbit-print-schema.sh"

run_test "test-workspace-map.sh"
run_test "test-build-contract.sh"
run_test "test-check-naming-no-rbt.sh"

echo "ALL TESTS PASSED"
