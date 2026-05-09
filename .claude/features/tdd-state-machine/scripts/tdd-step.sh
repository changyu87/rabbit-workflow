#!/bin/bash
# tdd-step.sh — read and transition the tdd_state of a feature.
#
# Usage:
#   tdd-step.sh show <feature-dir>
#   tdd-step.sh next <feature-dir>
#   tdd-step.sh transitions <feature-dir>
#   tdd-step.sh transition <feature-dir> <new-state> [--force]
#
# Exit:
#   0 success
#   1 transition denied or invalid input
#   2 invocation error

set -u

usage() {
  cat >&2 <<EOF
usage:
  tdd-step.sh show <feature-dir>
  tdd-step.sh next <feature-dir>
  tdd-step.sh transitions <feature-dir>
  tdd-step.sh transition <feature-dir> <new-state> [--force]
EOF
}

# Forward transitions only. Anything else requires --force.
forward_next() {
  case "$1" in
    spec)       echo "test-red" ;;
    test-red)   echo "impl" ;;
    impl)       echo "test-green" ;;
    test-green) echo "review" ;;
    review)     echo "merged" ;;
    merged)     echo "deprecated" ;;
    deprecated) echo "" ;;        # terminal
    *)          echo "" ;;
  esac
}

is_valid_state() {
  case "$1" in
    spec|test-red|impl|test-green|review|merged|deprecated) return 0 ;;
    *) return 1 ;;
  esac
}

read_state() {
  local dir="$1"
  [ -f "$dir/feature.json" ] || { echo "ERROR: no feature.json in $dir" >&2; return 2; }
  jq -r '.tdd_state // ""' "$dir/feature.json"
}

write_state() {
  local dir="$1" new="$2"
  local today; today="$(date +%Y-%m-%d)"
  jq --arg s "$new" --arg u "$today" '.tdd_state = $s | .updated = $u' \
    "$dir/feature.json" > "$dir/feature.json.tmp" \
    && mv "$dir/feature.json.tmp" "$dir/feature.json"
}

cmd="${1:-}"; shift || true

case "$cmd" in
  show)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    s=$(read_state "$dir") || exit $?
    echo "$s"
    ;;
  next)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    s=$(read_state "$dir") || exit $?
    n=$(forward_next "$s")
    [ -z "$n" ] && { echo "ERROR: $s is terminal, no forward state" >&2; exit 1; }
    echo "$n"
    ;;
  transitions)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    s=$(read_state "$dir") || exit $?
    n=$(forward_next "$s")
    if [ -n "$n" ]; then
      echo "$n"
    else
      echo "(terminal)"
    fi
    ;;
  transition)
    dir="${1:-}"; new="${2:-}"; flag="${3:-}"
    [ -z "$dir" ] || [ -z "$new" ] && { usage; exit 2; }
    is_valid_state "$new" || { echo "ERROR: '$new' is not a valid tdd_state" >&2; exit 1; }
    cur=$(read_state "$dir") || exit $?
    expected=$(forward_next "$cur")
    if [ "$cur" = "deprecated" ]; then
      echo "ERROR: '$cur' is terminal; cannot transition (even with --force)" >&2
      exit 1
    fi
    if [ "$new" = "$expected" ]; then
      write_state "$dir" "$new"
      echo "$cur -> $new"
      exit 0
    fi
    if [ "$flag" = "--force" ]; then
      write_state "$dir" "$new"
      echo "FORCED: $cur -> $new" >&2
      echo "$cur -> $new"
      exit 0
    fi
    echo "ERROR: $cur -> $new not allowed (forward expected: $expected). Use --force to override." >&2
    exit 1
    ;;
  ""|-h|--help|help)
    usage; [ -z "$cmd" ] && exit 2 || exit 0
    ;;
  *)
    echo "ERROR: unknown subcommand '$cmd'" >&2
    usage; exit 2
    ;;
esac
