#!/usr/bin/env bash
# dispatch-feature-tdd.sh — assemble the prompt for a per-feature full-TDD-cycle subagent.
#
# Usage:
#   dispatch-feature-tdd.sh <feature-name> "<request-description>" [--bug <bug-dir>] [--backlog <item-dir>]
#
# Output: assembled prompt to stdout. Caller passes stdout to Agent.
# The subagent runs spec-update → test-red → impl → test-green for the named feature.
#
# Optional flags (mutually exclusive):
#   --bug <bug-dir>       After test-green, close the bug at <bug-dir> with the impl commit SHA.
#   --backlog <item-dir>  After test-green, mark the backlog item at <item-dir> implemented
#                         with the impl commit SHA.
#
# Version: 1.1.0
# Owner: rabbit-workflow team (tdd-state-machine)
# Deprecation criterion: when the TDD cycle is natively supported by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"

if [ $# -lt 2 ]; then
  echo "ERROR: usage: dispatch-feature-tdd.sh <feature-name> <request-description> [--bug <bug-dir>] [--backlog <item-dir>]" >&2
  exit 2
fi

FEATURE_NAME="$1"
REQUEST="$2"
shift 2

BUG_DIR=""
BACKLOG_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --bug)
      [ -z "${2:-}" ] && { echo "ERROR: --bug requires a directory argument" >&2; exit 2; }
      BUG_DIR="$2"; shift 2 ;;
    --backlog)
      [ -z "${2:-}" ] && { echo "ERROR: --backlog requires a directory argument" >&2; exit 2; }
      BACKLOG_DIR="$2"; shift 2 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
FEATURE_PATH=$(bash "$FIND_FEATURE" "$FEATURE_NAME" 2>/dev/null) || {
  echo "ERROR: feature '$FEATURE_NAME' not found" >&2; exit 1
}

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
BUG_STATUS_SH="$REPO_ROOT/.claude/features/rabbit-bug/scripts/bug-status.sh"
BACKLOG_STATUS_SH="$REPO_ROOT/.claude/features/rabbit-backlog/scripts/backlog-item-status.sh"

# Build optional post-test-green status update block
STATUS_UPDATE_BLOCK=""
if [ -n "$BUG_DIR" ]; then
  STATUS_UPDATE_BLOCK="Step 8b: Close linked bug after test-green
  IMPL_SHA=\$(git -C ${REPO_ROOT} rev-parse HEAD)
  bash ${BUG_STATUS_SH} set ${BUG_DIR} closed --reason 'TDD cycle complete' --fix-commits \"\$IMPL_SHA\"
  linked_item: ${BUG_DIR} (status: closed)
"
elif [ -n "$BACKLOG_DIR" ]; then
  STATUS_UPDATE_BLOCK="Step 8b: Mark linked backlog item implemented after test-green
  IMPL_SHA=\$(git -C ${REPO_ROOT} rev-parse HEAD)
  bash ${BACKLOG_STATUS_SH} set ${BACKLOG_DIR} implemented --reason 'TDD cycle complete' --fix-commits \"\$IMPL_SHA\"
  linked_item: ${BACKLOG_DIR} (status: implemented)
"
fi

# Build HANDOFF linked_item line
HANDOFF_LINKED_ITEM=""
if [ -n "$BUG_DIR" ]; then
  HANDOFF_LINKED_ITEM="  linked_item: ${BUG_DIR} (status: closed)"
elif [ -n "$BACKLOG_DIR" ]; then
  HANDOFF_LINKED_ITEM="  linked_item: ${BACKLOG_DIR} (status: implemented)"
fi

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

${STATUS_UPDATE_BLOCK}Step 9: Scope marker removed by trap (EXIT fires automatically)

════════════════════════════════════════════════════════════════════════
HANDOFF (emit when complete)
════════════════════════════════════════════════════════════════════════

HANDOFF:
  feature: ${FEATURE_NAME}
  tdd_state: test-green
  spec_changed: <yes|no>
  test_result: pass
${HANDOFF_LINKED_ITEM}
  notes: <brief>

PROMPT

echo "dispatch-feature-tdd: prompt ready for feature '${FEATURE_NAME}'" >&2
