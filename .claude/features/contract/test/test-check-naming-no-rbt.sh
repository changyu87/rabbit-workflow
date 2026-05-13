#!/bin/bash
# test-check-naming-no-rbt.sh — assert that check-naming.sh contains no reference to
# 'rbt-' in any comment or flag message. The rbt- prefix is fully deprecated
# with no remaining valid use cases; all documentation in check-naming.sh must
# reflect that rabbit- (or no prefix) is current policy for all artifacts.
#
# Non-interactive. Exits non-zero on failure.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$FEATURE_DIR/scripts/enforcement/check-naming.sh"
PASS=0
FAIL=0

ok()   { echo "  PASS $1: $2"; PASS=$((PASS+1)); }
fail() { echo "  FAIL $1: $2" >&2; FAIL=$((FAIL+1)); }

# t1: the script exists (sanity check)
if [ -f "$SCRIPT" ]; then
  ok t1 "check-naming.sh exists"
else
  fail t1 "check-naming.sh missing at $SCRIPT"
fi

# t2: no occurrence of 'rbt-' in the file (comments, flag messages, or any line)
if grep -qF "rbt-" "$SCRIPT" 2>/dev/null; then
  fail t2 "check-naming.sh contains 'rbt-' reference (deprecated prefix must be removed from all comments and flag messages)"
else
  ok t2 "check-naming.sh contains no 'rbt-' reference"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
  echo "test-check-naming-no-rbt: FAIL" >&2
  exit 1
fi

echo "test-check-naming-no-rbt: all checks passed."
