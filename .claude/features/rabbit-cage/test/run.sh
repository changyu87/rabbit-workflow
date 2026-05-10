#!/usr/bin/env bash
# rabbit-cage test runner
# Executes all test scripts in sequence; exits non-zero on any failure.

set -euo pipefail

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

echo "rabbit-cage test runner"
echo ""

run_suite test-structure.sh
run_suite test-symlinks.sh
run_suite test-claude-md.sh
run_suite test-obsolete-removed.sh

if [ "$total_fail" -eq 0 ]; then
    echo "ALL SUITES PASSED"
    exit 0
else
    echo "FAILED: $total_fail suite(s) had failures"
    exit 1
fi
