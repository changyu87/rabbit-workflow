#!/usr/bin/env bash
# rbt-policy-check.sh — PreToolUse hook enforcing R6: every Agent dispatch must prepend
# the canonical policy block (sentinel: RABBIT-POLICY-BLOCK-v1).
#
# Fires on PreToolUse when tool_name == Agent.
# Exits 0 to allow; exits 2 to block with error message.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively enforces policy prepend for Agent calls.

set -u

INPUT="$(cat)"
TOOL_NAME="$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)"

# Only check Agent calls
[ "$TOOL_NAME" = "Agent" ] || exit 0

PROMPT="$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('prompt',''))" 2>/dev/null)"

if echo "$PROMPT" | grep -q "RABBIT-POLICY-BLOCK-v1"; then
    exit 0
fi

echo "rbt-policy-check: Agent call blocked — prompt missing RABBIT-POLICY-BLOCK-v1 sentinel. Per R6, all Agent dispatches must prepend the canonical policy block via policy-block.sh. Use dispatch-feature-edit.sh or rabbit-triage.sh to build the Agent prompt." >&2
exit 2
