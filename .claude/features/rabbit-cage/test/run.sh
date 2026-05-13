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

run_suite test-scope-guard-centralized.sh
run_suite test-structure.sh
run_suite test-claude-md.sh
run_suite test-obsolete-removed.sh
run_suite test-hook-enforcement.sh
run_suite test-generate-claude-md.sh
run_suite test-split-validation.sh
run_suite test-RABBIT-CAGE-15-workspace-tree.sh
run_suite test-generated-surface.sh
run_suite test-RABBIT-CAGE-16-first-stop-no-false-drift.sh
run_suite test-RABBIT-CAGE-BACKLOG7-visual-messages.sh
run_suite test-RABBIT-CAGE-BACKLOG9-green-messages.sh
run_suite test-RABBIT-CAGE-BACKLOG10-override.sh
run_suite test-RABBIT-CAGE-17-quoted-strings.sh
run_suite test-RABBIT-CAGE-18-scope-alert-messages.sh
run_suite test-scope-per-feature-marker.sh
run_suite test-RABBIT-CAGE-19-confirm-token-override.sh
run_suite test-scope-guard-allowlist.sh
run_suite test-rabbit-workspace-map-wiring.sh
run_suite test-POLICY-BACKLOG-1-session-init-branch.sh
run_suite test-build-non-git-dir.sh
run_suite test-rabbit-config.sh

if [ "$total_fail" -eq 0 ]; then
    echo "ALL SUITES PASSED"
    exit 0
else
    echo "FAILED: $total_fail suite(s) had failures"
    exit 1
fi
