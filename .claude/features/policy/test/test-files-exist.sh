#!/usr/bin/env bash
# test-files-exist.sh — Verifies all required policy files exist and are non-empty.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check_file() {
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

check_file "philosophy.md"
check_file "spec-rules.md"
check_file "coding-rules.md"
check_file "workflow-rules.md"
check_file "docs/spec/spec.md"
check_file "docs/spec/contract.md"
