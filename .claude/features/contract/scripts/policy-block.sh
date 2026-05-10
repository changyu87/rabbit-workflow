#!/bin/bash
# policy-block.sh — emit the canonical rabbit-workflow policy block to stdout.
#
# This block is the MANDATORY prepend for every Agent dispatch (rabbit's own
# subagents AND Claude's built-in ones). The dispatcher captures stdout and
# prepends to the prompt field of the Agent tool call. Per hard-rules R6.
#
# Usage:
#   policy-block.sh                                # philosophy.md + spec-rules.md + coding-rules.md + workflow-rules.md
#   policy-block.sh --include <path>               # plus the named file
#   policy-block.sh --include a --include b ...    # multiple includes compose
#
# Files are looked up at:
#   <repo>/.claude/features/policy/philosophy.md
#   <repo>/.claude/features/policy/spec-rules.md
#   <repo>/.claude/features/policy/coding-rules.md
#   <repo>/.claude/features/policy/workflow-rules.md
# where <repo> is computed from this script's location.
#
# Exit:
#   0 success
#   1 a --include path is missing
#   2 invocation error

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
POLICY_DIR="$REPO_ROOT/.claude/features/policy"
PHIL="$POLICY_DIR/philosophy.md"
SPEC_RULES="$POLICY_DIR/spec-rules.md"
CODING_RULES="$POLICY_DIR/coding-rules.md"
WORKFLOW_RULES="$POLICY_DIR/workflow-rules.md"

INCLUDES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --include)
      [ -z "${2:-}" ] && { echo "ERROR: --include requires a path arg" >&2; exit 2; }
      INCLUDES+=("$2"); shift 2
      ;;
    -h|--help)
      sed -n '2,22p' "$0" >&2
      exit 0
      ;;
    *)
      echo "ERROR: unknown arg '$1'" >&2
      exit 2
      ;;
  esac
done

# Validate all --include paths upfront so we error before emitting any output.
for p in "${INCLUDES[@]}"; do
  if [ ! -f "$p" ]; then
    echo "ERROR: --include path does not exist: $p" >&2
    exit 1
  fi
done

# Sanity: the canonical files must exist.
for f in "$PHIL" "$SPEC_RULES" "$CODING_RULES" "$WORKFLOW_RULES"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: missing canonical policy file: $f" >&2
    exit 1
  fi
done

# Emit the sentinel line first.
printf 'RABBIT-POLICY-BLOCK-v1\n'

# Emit the block header.
cat <<'EOF'
═══════════════════════════════════════════════════════════════════════════════
MANDATORY POLICY — READ THIS BEFORE ANY ACTION
═══════════════════════════════════════════════════════════════════════════════

You are operating within the rabbit workflow. The following policy files are
NOT optional reading. They govern every choice you make in this invocation.
Failure to comply is a constitution violation.

If you have not yet internalized these principles, STOP and read them now
before doing anything else. Re-read them whenever you are uncertain about
how to proceed. They are the source of truth for every decision in this
session.

EOF

emit_section() {
  local label="$1" path="$2"
  printf -- '────────────────── %s ──────────────────\n' "$label"
  cat "$path"
  printf '\n'
}

emit_section "philosophy.md" "$PHIL"
emit_section "spec-rules.md" "$SPEC_RULES"
emit_section "coding-rules.md" "$CODING_RULES"
emit_section "workflow-rules.md" "$WORKFLOW_RULES"

for p in "${INCLUDES[@]}"; do
  emit_section "$(basename "$p")" "$p"
done

cat <<'EOF'
═══════════════════════════════════════════════════════════════════════════════
END POLICY — proceed with your task. Honor the above in every action.
═══════════════════════════════════════════════════════════════════════════════
EOF

exit 0
