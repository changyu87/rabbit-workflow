#!/usr/bin/env bash
# test-r3-fullstack-e2e.sh — Verifies R3 in workflow-rules.md mandates full-stack E2E chain coverage.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$FEATURE_DIR/workflow-rules.md"

# R3 must explicitly mention full-stack/E2E chain coverage across all layers.
PHRASE="full-stack"

if ! grep -q "$PHRASE" "$FILE"; then
  echo "FAIL: '$PHRASE' not found in $FILE" >&2
  echo "R3 does not yet mandate full-stack E2E chain coverage." >&2
  exit 1
fi

echo "PASS: '$PHRASE' found in $FILE"
