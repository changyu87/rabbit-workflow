#!/usr/bin/env bash
# test-policy-invariants-v1-2-0.sh — Verifies spec v1.2.0 invariants:
#   (1) philosophy.md, spec-rules.md, coding-rules.md exist and are non-empty.
#   (2) workflow-rules.md does NOT exist.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check_exists_nonempty() {
  local rel="$1"
  local path="$FEATURE_DIR/$rel"
  if [ ! -f "$path" ]; then
    echo "FAIL: missing file: $path" >&2
    exit 1
  fi
  if [ ! -s "$path" ]; then
    echo "FAIL: empty file: $path" >&2
    exit 1
  fi
}

check_absent() {
  local rel="$1"
  local path="$FEATURE_DIR/$rel"
  if [ -f "$path" ]; then
    echo "FAIL: file must not exist: $path" >&2
    exit 1
  fi
}

# Invariant 1: three rule files exist and are non-empty
check_exists_nonempty "philosophy.md"
check_exists_nonempty "spec-rules.md"
check_exists_nonempty "coding-rules.md"

# Invariant 2: workflow-rules.md must NOT exist
check_absent "workflow-rules.md"

echo "All checks passed."
