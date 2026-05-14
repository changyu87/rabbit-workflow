#!/usr/bin/env bash
# test-workflow-rules-sections.sh — Verifies workflow-rules.md contains ONLY Section 4.
# After archival, the file retains only "Token/compliance tradeoff is the user's call".
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

check_phrase_absent() {
  local phrase="$1"
  if grep -q "$phrase" "$FILE"; then
    echo "FAIL: '$phrase' should NOT be in $FILE (sections removed in archival)" >&2
    exit 1
  fi
}

# Section 4 must be present
check_phrase "Token/compliance tradeoff"
check_phrase "if you touch a feature, run the full discipline"

# Archived sections must be absent
check_phrase_absent "Subagent-driven by construction"
check_phrase_absent "Full TDD on every feature touch"
check_phrase_absent "Hard rules index"
check_phrase_absent "Cross-component handoffs use schemas"

echo "All checks passed."
