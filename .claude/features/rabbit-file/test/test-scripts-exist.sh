#!/usr/bin/env bash
set -uo pipefail
FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$FEATURE_DIR/scripts"
pass=0; fail=0
assert_pass() { echo "PASS: $1"; pass=$((pass+1)); }
assert_fail() { echo "FAIL: $1 — $2"; fail=$((fail+1)); }

for s in branch_ops.py file-item.py item-status.py list-items.py; do
    if [ -f "$SCRIPTS/$s" ]; then assert_pass "$s exists"
    else assert_fail "$s exists" "missing at $SCRIPTS/$s"; fi
done

echo ""; echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
