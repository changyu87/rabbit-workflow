#!/usr/bin/env bash
# dispatch-spec-update.sh — assemble an Opus subagent prompt for the spec-update leg.
#
# Usage:
#   dispatch-spec-update.sh <feature-name> "<change-description>"
#
# Output: assembled prompt to stdout. Caller passes stdout to Agent with model: opus.
#
# Exit:
#   0 success (prompt printed to stdout)
#   1 feature not found in registry
#   2 invocation error
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when spec-update is superseded by a native spec-management tool.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"

if [ $# -ne 2 ]; then
  echo "ERROR: usage: dispatch-spec-update.sh <feature-name> <change-description>" >&2
  exit 2
fi

FEATURE_NAME="$1"
CHANGE_DESC="$2"

FIND_FEATURE="$SCRIPT_DIR/find-feature.sh"
FEATURE_PATH="$(bash "$FIND_FEATURE" "$FEATURE_NAME" 2>/dev/null)" || {
  echo "ERROR: feature '$FEATURE_NAME' not found in registry" >&2; exit 1
}

FEATURE_DIR="$REPO_ROOT/$FEATURE_PATH"
SPEC_PATH="$FEATURE_DIR/docs/spec/spec.md"
CONTRACT_PATH="$FEATURE_DIR/docs/spec/contract.md"
TEMPLATE="$SCRIPT_DIR/../templates/spec-update-template.txt"
POLICY_BLOCK_SH="$SCRIPT_DIR/policy-block.sh"

SPEC_CONTENT="(spec.md not found)"
[ -f "$SPEC_PATH" ] && SPEC_CONTENT="$(cat "$SPEC_PATH")"

CONTRACT_CONTENT="(contract.md not found)"
[ -f "$CONTRACT_PATH" ] && CONTRACT_CONTENT="$(cat "$CONTRACT_PATH")"

GIT_DIFF="$(git -C "$REPO_ROOT" diff HEAD -- "$FEATURE_PATH" 2>/dev/null | head -300 || echo "(no diff or git unavailable)")"

TEMPLATE_CONTENT="(spec-update-template.txt not found)"
[ -f "$TEMPLATE" ] && TEMPLATE_CONTENT="$(cat "$TEMPLATE")"

POLICY_BLOCK="$("$POLICY_BLOCK_SH" 2>/dev/null)"

cat <<PROMPT
${POLICY_BLOCK}

═══════════════════════════════════════════════════════════════════════════════
SCOPE DECLARATION
═══════════════════════════════════════════════════════════════════════════════

SCOPE: ${FEATURE_NAME}

You are a scoped subagent. Write ONLY inside: ${FEATURE_DIR}/docs/spec/
The .rabbit-scope-active marker must be set by the caller before Agent dispatch.

═══════════════════════════════════════════════════════════════════════════════
CURRENT SPEC
═══════════════════════════════════════════════════════════════════════════════

${SPEC_CONTENT}

═══════════════════════════════════════════════════════════════════════════════
CURRENT CONTRACT
═══════════════════════════════════════════════════════════════════════════════

${CONTRACT_CONTENT}

═══════════════════════════════════════════════════════════════════════════════
IMPLEMENTATION DIFF SINCE LAST test-green
═══════════════════════════════════════════════════════════════════════════════

${GIT_DIFF}

═══════════════════════════════════════════════════════════════════════════════
CHANGE DESCRIPTION
═══════════════════════════════════════════════════════════════════════════════

${CHANGE_DESC}

═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════

${TEMPLATE_CONTENT}
PROMPT
echo "dispatch-spec-update: prompt ready for feature '${FEATURE_NAME}' — caller passes stdout to Agent with model: opus." >&2
