#!/bin/bash
# validate-all.sh — sweep validate-feature.sh across every feature directory
# under a given root. Useful in user mode to validate "all features in my
# project" with a single call.
#
# Usage:
#   validate-all.sh [<features-root>] [--validator <path>]
#
# Default <features-root> is $FEATURES_ROOT, then ".claude/features".
# Default --validator is autodetected (well-known relative paths).
#
# Exit:
#   0 all features pass (or no features found)
#   1 one or more features fail
#   2 validator not found / invocation error

set -u

ROOT=""; VALIDATOR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --validator) VALIDATOR="$2"; shift 2 ;;
    -h|--help)
      echo "usage: validate-all.sh [<features-root>] [--validator <path>]" >&2
      exit 0 ;;
    -*) echo "unknown arg: $1" >&2; exit 2 ;;
    *)  ROOT="$1"; shift ;;
  esac
done

ROOT="${ROOT:-${FEATURES_ROOT:-.claude/features}}"

# Autodetect validator if not given
if [ -z "$VALIDATOR" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  for candidate in \
      "$SCRIPT_DIR/../../feature-skeleton/scripts/validate-feature.sh" \
      ".claude/features/feature-skeleton/scripts/validate-feature.sh"; do
    if [ -x "$candidate" ]; then VALIDATOR="$candidate"; break; fi
  done
fi

if [ -z "$VALIDATOR" ] || [ ! -x "$VALIDATOR" ]; then
  echo "ERROR: validate-feature.sh not found (set --validator <path> or install feature-skeleton)" >&2
  exit 2
fi

# Vacuous pass if root doesn't exist or is empty
if [ ! -d "$ROOT" ]; then
  echo "OK: features root '$ROOT' does not exist (vacuous pass)"
  exit 0
fi

shopt -s nullglob
features=()
for d in "$ROOT"/*/; do
  [ -f "${d}feature.json" ] || continue   # skip non-feature subdirs
  features+=("$d")
done

if [ "${#features[@]}" -eq 0 ]; then
  echo "OK: no features found under '$ROOT' (vacuous pass)"
  exit 0
fi

passed=0; failed=0; failed_names=()
for d in "${features[@]}"; do
  name="$(basename "$d")"
  if "$VALIDATOR" "${d%/}" >/dev/null 2>&1; then
    echo "  PASS: $name"
    passed=$((passed+1))
  else
    echo "  FAIL: $name"
    failed=$((failed+1))
    failed_names+=("$name")
  fi
done

echo
echo "summary: $passed passed, $failed failed (root: $ROOT)"
if [ "$failed" -gt 0 ]; then
  echo "failed features: ${failed_names[*]}" >&2
  exit 1
fi
exit 0
