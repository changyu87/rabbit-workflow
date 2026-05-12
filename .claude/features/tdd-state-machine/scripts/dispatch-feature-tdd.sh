#!/usr/bin/env bash
# dispatch-feature-tdd.sh — assemble the prompt for a per-feature full-TDD-cycle subagent.
#
# Usage:
#   dispatch-feature-tdd.sh <feature-name> "<request-description>"
#
# Output: assembled prompt to stdout. Caller passes stdout to Agent.
# The subagent runs spec-update → test-red → impl → test-green for the named feature.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (tdd-state-machine)
# Deprecation criterion: when the TDD cycle is natively supported by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"

if [ $# -ne 2 ]; then
  echo "ERROR: usage: dispatch-feature-tdd.sh <feature-name> <request-description>" >&2
  exit 2
fi

FEATURE_NAME="$1"
REQUEST="$2"

REGISTRY="$REPO_ROOT/.claude/features/registry.json"
[ -f "$REGISTRY" ] || { echo "ERROR: registry.json not found" >&2; exit 1; }

FEATURE_PATH=$(python3 -c "import json; r=json.load(open('$REGISTRY')); print(r.get('features',{}).get('$FEATURE_NAME',{}).get('path',''))" 2>/dev/null)
[ -z "$FEATURE_PATH" ] && { echo "ERROR: feature '$FEATURE_NAME' not found in registry" >&2; exit 1; }

FEATURE_DIR="$REPO_ROOT/$FEATURE_PATH"
SPEC_PATH="$FEATURE_DIR/docs/spec/spec.md"
CONTRACT_PATH="$FEATURE_DIR/docs/spec/contract.md"

SPEC_CONTENT="(spec.md not found)"
[ -f "$SPEC_PATH" ] && SPEC_CONTENT="$(cat "$SPEC_PATH")"

CONTRACT_CONTENT="(contract.md not found)"
[ -f "$CONTRACT_PATH" ] && CONTRACT_CONTENT="$(cat "$CONTRACT_PATH")"

POLICY_BLOCK_SH="$REPO_ROOT/.claude/features/contract/scripts/policy-block.sh"
POLICY_BLOCK=""
[ -f "$POLICY_BLOCK_SH" ] && POLICY_BLOCK="$("$POLICY_BLOCK_SH" 2>/dev/null)"

DISPATCH_SPEC_SH="$REPO_ROOT/.claude/features/contract/scripts/dispatch-spec-update.sh"
DISPATCH_EDIT_SH="$REPO_ROOT/.claude/features/contract/scripts/dispatch-feature-edit.sh"
TDD_STEP_SH="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-step.sh"

cat <<PROMPT
RABBIT-POLICY-BLOCK-v1
${POLICY_BLOCK}

════════════════════════════════════════════════════════════════════════
SCOPE DECLARATION
════════════════════════════════════════════════════════════════════════

SCOPE: ${FEATURE_NAME}

You are a per-feature TDD orchestrator subagent. You run the FULL TDD cycle
(spec-update → test-red → impl → test-green) for the feature declared above.

You use the per-feature scope marker for parallel-safe operation:
  touch ${REPO_ROOT}/.rabbit-scope-active-${FEATURE_NAME}

Set this marker as your FIRST action. Remove it as your LAST action (trap EXIT).
This enables parallel dispatch alongside agents for other features.

════════════════════════════════════════════════════════════════════════
REQUEST
════════════════════════════════════════════════════════════════════════

${REQUEST}

════════════════════════════════════════════════════════════════════════
FEATURE SPEC
════════════════════════════════════════════════════════════════════════

${SPEC_CONTENT}

════════════════════════════════════════════════════════════════════════
FEATURE CONTRACT
════════════════════════════════════════════════════════════════════════

${CONTRACT_CONTENT}

════════════════════════════════════════════════════════════════════════
TDD CYCLE — EXECUTE IN ORDER
════════════════════════════════════════════════════════════════════════

Step 0: Set scope marker
  touch ${REPO_ROOT}/.rabbit-scope-active-${FEATURE_NAME}
  trap 'rm -f ${REPO_ROOT}/.rabbit-scope-active-${FEATURE_NAME}' EXIT

Step 1: Force to spec-update
  bash ${TDD_STEP_SH} transition ${FEATURE_DIR} spec-update --force

Step 2: Dispatch SPEC-UPDATE subagent (Opus — R2)
  PROMPT=\$(bash ${DISPATCH_SPEC_SH} ${FEATURE_NAME} "<summarize what the request requires>")
  Dispatch Agent(model: opus, prompt: PROMPT)
  Read HANDOFF — verify spec_changes field present.

Step 3: Read spec git diff
  git diff HEAD -- ${FEATURE_DIR}/docs/spec/

Step 4: Advance to test-red
  bash ${TDD_STEP_SH} transition ${FEATURE_DIR} test-red
  (or with --spec-no-change-reason "<reason>" if spec was unchanged)

Step 5: Dispatch TEST subagent
  PROMPT=\$(bash ${DISPATCH_EDIT_SH} ${FEATURE_NAME} "Write failing tests only. Assert spec invariants. Do NOT implement. Run tests, confirm they fail.")
  Dispatch Agent(prompt: PROMPT)
  Read HANDOFF — verify test_result: fail.

Step 6: Advance to impl
  bash ${TDD_STEP_SH} transition ${FEATURE_DIR} impl

Step 7: Dispatch IMPLEMENTATION subagent
  PROMPT=\$(bash ${DISPATCH_EDIT_SH} ${FEATURE_NAME} "Implement to make tests pass. Follow spec invariants. Run all tests, confirm pass. Then: bash ${TDD_STEP_SH} transition ${FEATURE_DIR} test-green")
  Dispatch Agent(prompt: PROMPT)

Step 8: Verify test-green
  bash ${TDD_STEP_SH} show ${FEATURE_DIR}  # must output: test-green

Step 9: Scope marker removed by trap (EXIT fires automatically)

════════════════════════════════════════════════════════════════════════
HANDOFF (emit when complete)
════════════════════════════════════════════════════════════════════════

HANDOFF:
  feature: ${FEATURE_NAME}
  tdd_state: test-green
  spec_changed: <yes|no>
  test_result: pass
  notes: <brief>

PROMPT

echo "dispatch-feature-tdd: prompt ready for feature '${FEATURE_NAME}'" >&2
