#!/bin/bash
# Test that R8 and R9 are present and contain the required key phrases in hard-rules spec.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPEC="$SCRIPT_DIR/../docs/spec/spec.md"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

grep -q "R8" "$SPEC" \
  && ok "spec contains R8" \
  || ko "spec missing R8"

grep -q "R9" "$SPEC" \
  && ok "spec contains R9" \
  || ko "spec missing R9"

grep -q "full TDD" "$SPEC" \
  && ok "spec contains 'full TDD'" \
  || ko "spec missing 'full TDD'"

grep -q "project-level contract" "$SPEC" \
  && ok "spec contains 'project-level contract'" \
  || ko "spec missing 'project-level contract'"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
