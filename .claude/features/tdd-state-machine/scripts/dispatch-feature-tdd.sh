#!/usr/bin/env bash
# dispatch-feature-tdd.sh — assemble the prompt for a per-feature full-TDD-cycle subagent.
#
# Usage:
#   dispatch-feature-tdd.sh <feature-name> "<request-description>" [--linked-item <dir> --item-type <bug|backlog>]
#
# Output: assembled prompt to stdout. Caller passes stdout to Agent.
# The subagent runs spec-update → test-red → impl → test-green for the named feature,
# then writes tdd-report.json to .rabbit/tdd-report.json. The calling skill handles status updates.
#
# Optional flags:
#   --linked-item <dir>   Directory of the linked bug or backlog item.
#   --item-type <type>    Required with --linked-item: bug|backlog
#
# Version: 2.0.0
# Owner: rabbit-workflow team (tdd-state-machine)
# Deprecation criterion: when the TDD cycle is natively supported by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"

if [ $# -lt 2 ]; then
  echo "ERROR: usage: dispatch-feature-tdd.sh <feature-name> <request-description> [--linked-item <dir> --item-type <bug|backlog>]" >&2
  exit 2
fi

FEATURE_NAME="$1"
REQUEST="$2"
shift 2

LINKED_ITEM_DIR=""
ITEM_TYPE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --linked-item)
      [ -z "${2:-}" ] && { echo "ERROR: --linked-item requires a directory argument" >&2; exit 2; }
      LINKED_ITEM_DIR="$2"; shift 2 ;;
    --item-type)
      [ -z "${2:-}" ] && { echo "ERROR: --item-type requires bug|backlog" >&2; exit 2; }
      ITEM_TYPE="$2"; shift 2 ;;
    --bug|--backlog)
      echo "ERROR: $1 is removed. Use --linked-item <dir> --item-type <bug|backlog>" >&2
      exit 2 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [ -n "$LINKED_ITEM_DIR" ] && [ -z "$ITEM_TYPE" ]; then
  echo "ERROR: --linked-item requires --item-type <bug|backlog>" >&2; exit 2
fi
if [ -n "$ITEM_TYPE" ] && [ -z "$LINKED_ITEM_DIR" ]; then
  echo "ERROR: --item-type requires --linked-item <dir>" >&2; exit 2
fi

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

Step 7b: Inline spec-review (performed by you — do NOT dispatch another Agent)
  Read: ${SPEC_PATH}
  Run:  git diff HEAD -- ${FEATURE_DIR}/
  Compare each spec invariant to the implementation diff.
  Produce two values:
    spec_compliance: "pass" if all invariants addressed, "fail" if any are missing
    spec_compliance_notes: list any unaddressed invariants, or null if pass

Step 8: Write tdd-report.json to .rabbit/ (gitignored — NEVER commit this file)
  mkdir -p ${REPO_ROOT}/.rabbit/
  Path: ${REPO_ROOT}/.rabbit/tdd-report.json
  Write exactly this JSON schema:
  {
    "schema_version": "1.0.0",
    "feature": "${FEATURE_NAME}",
    "request": "<original request text>",
    "linked_item": "${LINKED_ITEM_DIR:-null}",
    "item_type": "${ITEM_TYPE:-null}",
    "spec_changes": "<yes|no>",
    "spec_no_change_reason": "<reason or null>",
    "test_gap_analysis": "<what was missing in test coverage before this fix, or 'none'>",
    "impl_summary": "<one paragraph describing what was implemented>",
    "spec_compliance": "<pass|fail>",
    "spec_compliance_notes": "<unaddressed invariants or null>",
    "test_result": "pass",
    "tdd_state": "test-green",
    "impl_commit": "<output of: git rev-parse HEAD>"
  }

Step 9: Scope marker removed by trap (EXIT fires automatically)

════════════════════════════════════════════════════════════════════════
HANDOFF (emit when complete)
════════════════════════════════════════════════════════════════════════

HANDOFF:
  feature: ${FEATURE_NAME}
  tdd_state: test-green
  test_result: pass
  spec_compliance: <pass|fail>
  tdd_report_path: ${REPO_ROOT}/.rabbit/tdd-report.json
  notes: <brief summary>

PROMPT

echo "dispatch-feature-tdd: prompt ready for feature '${FEATURE_NAME}'" >&2
