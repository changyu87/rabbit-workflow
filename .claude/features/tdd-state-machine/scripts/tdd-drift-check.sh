#!/bin/bash
# tdd-drift-check.sh — verify a feature's claimed tdd_state matches reality.
#
# Rules:
#   spec        : not test-checked (no claim about test outcome)
#   spec-update : not test-checked (no claim about test outcome)
#   test-red    : test/run.sh MUST exit non-zero
#   impl        : transitional; no test-outcome check
#   test-green  : test/run.sh MUST exit 0
#   deprecated  : not test-checked (terminal)
#
# Usage: tdd-drift-check.sh <feature-dir>
# Exit:  0 ok; 1 drift detected; 2 invocation error.

set -u

dir="${1:-}"
[ -z "$dir" ] && { echo "usage: tdd-drift-check.sh <feature-dir>" >&2; exit 2; }
[ ! -d "$dir" ] && { echo "ERROR: not a directory: $dir" >&2; exit 2; }
[ ! -f "$dir/feature.json" ] && { echo "ERROR: missing feature.json in $dir" >&2; exit 2; }

state=$(jq -r '.tdd_state // ""' "$dir/feature.json")
runner="$dir/test/run.sh"

run_tests_get_rc() {
  if [ ! -x "$runner" ]; then
    echo "ERROR: $runner missing or not executable" >&2
    return 2
  fi
  bash "$runner" >/dev/null 2>&1
  echo $?
}

case "$state" in
  spec|spec-update|impl|deprecated)
    echo "OK ($state, no test-outcome check)"
    exit 0
    ;;
  test-red)
    rc=$(run_tests_get_rc) || exit $?
    if [ "$rc" = "0" ]; then
      echo "DRIFT: claim 'test-red' but tests passed (rc=0). Either advance to test-green or restore failing tests." >&2
      exit 1
    fi
    echo "OK (test-red, tests failing as expected, rc=$rc)"
    exit 0
    ;;
  test-green)
    rc=$(run_tests_get_rc) || exit $?
    if [ "$rc" != "0" ]; then
      echo "DRIFT: claim '$state' but tests failed (rc=$rc). Either fix tests or transition back." >&2
      exit 1
    fi
    echo "OK ($state, tests passing)"
    exit 0
    ;;
  "")
    echo "ERROR: feature.json has no tdd_state" >&2
    exit 2
    ;;
  *)
    echo "ERROR: unknown tdd_state '$state'" >&2
    exit 2
    ;;
esac
