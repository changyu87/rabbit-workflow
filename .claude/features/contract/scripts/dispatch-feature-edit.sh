#!/bin/bash
# dispatch-feature-edit.sh — the only legal Agent dispatch path for feature edits.
#
# Usage:
#   dispatch-feature-edit.sh <feature-name> <task-description>
#
# Reads registry.json to find the feature root, sets a scope marker, builds
# the policy block, and prints the assembled prompt to stdout. The caller
# passes stdout as the prompt field to an Agent call. This script never
# invokes Agent directly — keeping it deterministic and testable.
#
# Exit:
#   0 success (prompt printed to stdout)
#   1 feature not found in registry
#   2 invocation error

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"

if [ $# -lt 2 ]; then
  echo "ERROR: usage: dispatch-feature-edit.sh <feature-name> <task-description>" >&2
  exit 2
fi

FEATURE_NAME="$1"
TASK_DESC="$2"

# Find registry.json — try the canonical location first.
REGISTRY="$REPO_ROOT/.claude/features/registry.json"
if [ ! -f "$REGISTRY" ]; then
  # Fallback: try project-level features directory.
  REGISTRY="$REPO_ROOT/features/registry.json"
fi
if [ ! -f "$REGISTRY" ]; then
  echo "ERROR: registry.json not found (tried .claude/features/registry.json and features/registry.json)" >&2
  exit 1
fi

# Extract feature path from registry (requires python3 or jq).
if command -v python3 >/dev/null 2>&1; then
  FEATURE_PATH="$(python3 -c "
import json, sys
reg = json.load(open('$REGISTRY'))
features = reg.get('features', {})
entry = features.get('$FEATURE_NAME')
if not entry:
    sys.exit(1)
print(entry.get('root', ''))
" 2>/dev/null)"
  PY_EXIT=$?
  if [ $PY_EXIT -ne 0 ] || [ -z "$FEATURE_PATH" ]; then
    echo "ERROR: feature '$FEATURE_NAME' not found in registry: $REGISTRY" >&2
    exit 1
  fi
elif command -v jq >/dev/null 2>&1; then
  FEATURE_PATH="$(jq -r ".features[\"$FEATURE_NAME\"].root // empty" "$REGISTRY" 2>/dev/null)"
  if [ -z "$FEATURE_PATH" ]; then
    echo "ERROR: feature '$FEATURE_NAME' not found in registry: $REGISTRY" >&2
    exit 1
  fi
else
  echo "ERROR: neither python3 nor jq found; cannot parse registry" >&2
  exit 1
fi

SCOPE_MARKER="$REPO_ROOT/.rabbit-scope-active"

# Set scope marker; remove it in a trap.
echo "$FEATURE_NAME" > "$SCOPE_MARKER"
cleanup() {
  rm -f "$SCOPE_MARKER"
}
trap cleanup EXIT INT TERM

# Build policy block.
POLICY_BLOCK="$("$SCRIPT_DIR/policy-block.sh")"

# Load feature spec and contract if available.
FEATURE_DIR="$REPO_ROOT/$FEATURE_PATH"
SPEC_PATH="$FEATURE_DIR/docs/spec/spec.md"
CONTRACT_PATH="$FEATURE_DIR/docs/spec/contract.md"

FEATURE_SPEC=""
if [ -f "$SPEC_PATH" ]; then
  FEATURE_SPEC="$(cat "$SPEC_PATH")"
fi

FEATURE_CONTRACT=""
if [ -f "$CONTRACT_PATH" ]; then
  FEATURE_CONTRACT="$(cat "$CONTRACT_PATH")"
fi

# Assemble prompt — prints to stdout for caller to pass as Agent prompt field.
cat <<PROMPT
RABBIT-POLICY-BLOCK-v1
$POLICY_BLOCK

═══════════════════════════════════════════════════════════════════════════════
SCOPE DECLARATION
═══════════════════════════════════════════════════════════════════════════════

SCOPE: $FEATURE_NAME

═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════

$TASK_DESC

═══════════════════════════════════════════════════════════════════════════════
FEATURE SPEC
═══════════════════════════════════════════════════════════════════════════════

$FEATURE_SPEC

═══════════════════════════════════════════════════════════════════════════════
FEATURE CONTRACT
═══════════════════════════════════════════════════════════════════════════════

$FEATURE_CONTRACT
PROMPT

echo "dispatch-feature-edit: prompt ready for feature '$FEATURE_NAME' — caller passes stdout to Agent." >&2

exit 0
