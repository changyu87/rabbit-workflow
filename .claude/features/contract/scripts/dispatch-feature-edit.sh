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

BUG_DIR=""
# Parse --bug before main args
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --bug) BUG_DIR="$2"; shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
set -- "${ARGS[@]}"

if [ $# -lt 2 ]; then
  echo "ERROR: usage: dispatch-feature-edit.sh [--bug <bug-dir>] <feature-name> <task-description>" >&2
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
print(entry.get('path', ''))
" 2>/dev/null)"
  PY_EXIT=$?
  if [ $PY_EXIT -ne 0 ] || [ -z "$FEATURE_PATH" ]; then
    echo "ERROR: feature '$FEATURE_NAME' not found in registry: $REGISTRY" >&2
    exit 1
  fi
elif command -v jq >/dev/null 2>&1; then
  FEATURE_PATH="$(jq -r ".features[\"$FEATURE_NAME\"].path // empty" "$REGISTRY" 2>/dev/null)"
  if [ -z "$FEATURE_PATH" ]; then
    echo "ERROR: feature '$FEATURE_NAME' not found in registry: $REGISTRY" >&2
    exit 1
  fi
else
  echo "ERROR: neither python3 nor jq found; cannot parse registry" >&2
  exit 1
fi

# Build TDD_GAP_REFLECTION if --bug was provided.
TDD_GAP_REFLECTION=""
if [ -n "$BUG_DIR" ]; then
  [ -d "$BUG_DIR" ] || { echo "ERROR: --bug dir not found: $BUG_DIR" >&2; exit 2; }
  [ -f "$BUG_DIR/bug.json" ] || { echo "ERROR: --bug dir missing bug.json: $BUG_DIR" >&2; exit 2; }
  BUG_ID="$(jq -r '.id // .bug_id // "unknown"' "$BUG_DIR/bug.json" 2>/dev/null)"
  BUG_TITLE="$(jq -r '.title // .summary // "unknown"' "$BUG_DIR/bug.json" 2>/dev/null)"
  TDD_GAP_REFLECTION="$(cat <<TDDBLOCK
═══════════════════════════════════════════════════════════════════════════════
TDD-GAP REFLECTION — MANDATORY FOR BUG FIXES
═══════════════════════════════════════════════════════════════════════════════

Bug: ${BUG_ID} — ${BUG_TITLE}

A bug reaching open status means the test suite did not catch it. Fixing
the symptom without closing the test gap is incomplete work — the same class
of regression will land again.

Before you may emit your final HANDOFF, you MUST:

  1. Identify the test that SHOULD have caught this bug.
       - If a test existed but did not exercise the failing path, name it.
       - If no test existed for this behavior, state: "none existed."

  2. Add (or extend) a test under the feature's test/ that fails against
     the un-fixed code and passes against your fix. Name the test after
     the bug id (e.g. test-${BUG_ID}-<description>.sh).

  3. Verify both directions:
       - Without your fix: the new test MUST fail.
       - With your fix:    the new test MUST pass.

  4. Include a TDD_GAP: block inside your HANDOFF (see handoff template).

If the bug is genuinely untestable, set existed: untestable and explain.
"Hard to test" is not "untestable." Main session will refuse a HANDOFF
that omits TDD_GAP for a bug-fix dispatch.
TDDBLOCK
)"
fi

# Detect if this is a project feature (lives under project-*/features/).
PROJECT_CONTRACT=""
case "$FEATURE_PATH" in
  project-*/features/*)
    PROJECT_ROOT="$(echo "$FEATURE_PATH" | sed 's|/features/.*||')"
    if [ -d "$REPO_ROOT/$PROJECT_ROOT/contract" ]; then
      PROJECT_CONTRACT="$REPO_ROOT/$PROJECT_ROOT/contract"
    fi
    ;;
esac

SCOPE_MARKER="$REPO_ROOT/.rabbit-scope-active"

# Set scope marker; remove it in a trap.
echo "$FEATURE_NAME" > "$SCOPE_MARKER"
cleanup() {
  rm -f "$SCOPE_MARKER"
}
trap cleanup EXIT INT TERM

# Build policy block (strip leading sentinel line — template emits it as line 1).
POLICY_BLOCK="$("$SCRIPT_DIR/policy-block.sh" | sed '1s/^RABBIT-POLICY-BLOCK-v1$//')"

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

# Load project-level contract if present (project contract wins over rabbit contract at conflict).
PROJECT_CONTRACT_CONTENT=""
if [ -n "$PROJECT_CONTRACT" ]; then
  PROJECT_CONTRACT_CONTENT="$(ls "$PROJECT_CONTRACT"/*.md 2>/dev/null | xargs cat 2>/dev/null || true)"
fi

# Assemble prompt — prints to stdout for caller to pass as Agent prompt field.
# Load the launch template and substitute placeholders.
TEMPLATE_PATH="$SCRIPT_DIR/../templates/subagent-launch-template.txt"
if [ -f "$TEMPLATE_PATH" ]; then
  PROMPT_TEXT="$(cat "$TEMPLATE_PATH")"
  PROMPT_TEXT="${PROMPT_TEXT//\{\{POLICY_BLOCK\}\}/$POLICY_BLOCK}"
  PROMPT_TEXT="${PROMPT_TEXT//\{\{feature_name\}\}/$FEATURE_NAME}"
  PROMPT_TEXT="${PROMPT_TEXT//\{\{task_description\}\}/$TASK_DESC}"
  PROMPT_TEXT="${PROMPT_TEXT//\{\{tdd_gap_reflection\}\}/$TDD_GAP_REFLECTION}"
  PROMPT_TEXT="${PROMPT_TEXT//\{\{feature_spec\}\}/$FEATURE_SPEC}"
  PROMPT_TEXT="${PROMPT_TEXT//\{\{feature_contract\}\}/$FEATURE_CONTRACT}"
  PROMPT_TEXT="${PROMPT_TEXT//\{\{project_contract\}\}/$PROJECT_CONTRACT_CONTENT}"
  printf '%s\n' "$PROMPT_TEXT"
else
  # Fallback: build prompt inline (template missing).
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

$TDD_GAP_REFLECTION
═══════════════════════════════════════════════════════════════════════════════
FEATURE SPEC
═══════════════════════════════════════════════════════════════════════════════

$FEATURE_SPEC

═══════════════════════════════════════════════════════════════════════════════
FEATURE CONTRACT
═══════════════════════════════════════════════════════════════════════════════

$FEATURE_CONTRACT
PROMPT
fi

echo "dispatch-feature-edit: prompt ready for feature '$FEATURE_NAME' — caller passes stdout to Agent." >&2

exit 0
