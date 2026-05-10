#!/usr/bin/env bash
# rabbit-cage test runner
# tdd_state: spec — tests not yet written; exits non-zero by design.

set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "rabbit-cage test runner"
echo "tdd_state: spec"
echo ""
echo "FAIL: tests not yet written"
exit 1
