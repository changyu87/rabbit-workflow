#!/usr/bin/env bash
# rabbit-bug test runner
# Executes all test suites in sequence; exits non-zero on any failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

total_fail=0

run_suite() {
    local script="$1"
    echo "=== $script ==="
    if bash "$SCRIPT_DIR/$script"; then
        echo ""
    else
        total_fail=$((total_fail + 1))
        echo ""
    fi
}

echo "rabbit-bug test runner"
echo ""

run_suite test-bug-scripts.sh
run_suite test-bug-skill.sh
run_suite test-bug-changes.sh
run_suite test-bug-git-isolation.sh

if [ "$total_fail" -eq 0 ]; then
    echo "ALL SUITES PASSED"
    exit 0
else
    echo "FAILED: $total_fail suite(s) had failures"
    exit 1
fi
