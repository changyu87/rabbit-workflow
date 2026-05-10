#!/usr/bin/env bash
# test-workflow-rules-sections.sh — Verifies workflow-rules.md contains all required sections.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$FEATURE_DIR/workflow-rules.md"

check_phrase() {
  local phrase="$1"
  if ! grep -q "$phrase" "$FILE"; then
    echo "FAIL: '$phrase' not found in $FILE" >&2
    exit 1
  fi
}

check_phrase "Subagent-driven by construction"
check_phrase "Full TDD on every feature touch"
check_phrase "Token/compliance tradeoff"
check_phrase "Hard rules index"
check_phrase "Cross-component handoffs use schemas"
check_phrase "R8"
check_phrase "R9"
