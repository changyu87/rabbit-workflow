#!/bin/bash
# check-tests-non-interactive.sh — fail if any test file under <feature-dir>/test/
# uses interactive constructs (read prompts, select menus, etc.) that would
# block an end-to-end run.
#
# Per the rabbit workflow rule: "for TDD steps, when you do test, it must be a
# hard end-to-end test with no human intervention."
#
# Usage: check-tests-non-interactive.sh <feature-dir>
# Exit:  0 ok (no test/ dir, or test/ clean); 1 violations found.

set -u

dir="${1:-}"
[ -z "$dir" ] && { echo "usage: check-tests-non-interactive.sh <feature-dir>" >&2; exit 2; }

testdir="$dir/test"
[ ! -d "$testdir" ] && { echo "OK: no test/ in $dir (vacuous)"; exit 0; }

# Patterns that indicate interactive input. Match only outside comments.
# Strategy: strip leading-whitespace + comment lines, then grep on remaining code.
violations=0
for f in $(find "$testdir" -type f -name '*.sh' 2>/dev/null); do
  # Strip lines that are pure comments (leading whitespace then #).
  code="$(grep -vE '^[[:space:]]*#' "$f")"

  # Check forbidden constructs.
  if echo "$code" | grep -qE '(^|[[:space:]])read([[:space:]]|$)'; then
    echo "VIOLATION: $f uses 'read' (would block waiting for input)." >&2
    violations=$((violations+1))
    continue
  fi
  if echo "$code" | grep -qE '(^|[[:space:]])select[[:space:]]+[A-Za-z_]+[[:space:]]+in'; then
    echo "VIOLATION: $f uses 'select ... in' (interactive menu)." >&2
    violations=$((violations+1))
    continue
  fi
  if echo "$code" | grep -qE '(^|[[:space:]])dialog([[:space:]]|$)'; then
    echo "VIOLATION: $f uses 'dialog' (interactive UI)." >&2
    violations=$((violations+1))
    continue
  fi
done

if [ "$violations" -gt 0 ]; then
  echo "FAIL: $violations interactive construct(s) found in $testdir." >&2
  exit 1
fi

echo "OK: no interactive constructs in $testdir"
exit 0
