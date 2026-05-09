#!/usr/bin/env bash
# test-rule-files-content.sh — Spot-checks content of the four rule files.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check_phrase() {
  local file="$1"
  local phrase="$2"
  local path="$FEATURE_DIR/$file"
  if ! grep -q "$phrase" "$path"; then
    echo "FAIL: '$phrase' not found in $path" >&2
    exit 1
  fi
}

# spec-rules.md
check_phrase "spec-rules.md" "Tool-Choice Tier"
check_phrase "spec-rules.md" "Schemas and Contracts"
check_phrase "spec-rules.md" "Lifecycle and Ownership"

# coding-rules.md
check_phrase "coding-rules.md" "Think Before Coding"
check_phrase "coding-rules.md" "Simplicity First"
check_phrase "coding-rules.md" "Karpathy"

# philosophy.md
check_phrase "philosophy.md" "Machine First"
check_phrase "philosophy.md" "Bounded Scope"
check_phrase "philosophy.md" "Designed Deprecation"
