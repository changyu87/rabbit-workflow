#!/usr/bin/env bash
# generate-claude-md.sh — generate CLAUDE.md header + @-import pointers.
#
# Reads the header line from policy-header.json; emits a CLAUDE.md that uses
# @-import pointers to the four policy files (no inline policy content).
#
# Usage:
#   generate-claude-md.sh                    # emit to stdout
#   generate-claude-md.sh --write [TARGET]   # write to TARGET/CLAUDE.md (default: REPO_ROOT)
#
# Version: 2.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively manages CLAUDE.md generation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
POLICY_HEADER_JSON="$SCRIPT_DIR/../policy-header.json"

WRITE_MODE=0
TARGET_ROOT="$REPO_ROOT"

while [ $# -gt 0 ]; do
  case "$1" in
    --write) WRITE_MODE=1; TARGET_ROOT="${2:-$REPO_ROOT}"; [ $# -gt 1 ] && shift; shift ;;
    *) echo "ERROR: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

HEADER="$(python3 -c "import json; print(json.load(open('$POLICY_HEADER_JSON'))['header'])")"

emit() {
  printf '%s\n' "$HEADER"
  printf '\n'
  printf '@.claude/features/policy/philosophy.md\n'
  printf '@.claude/features/policy/spec-rules.md\n'
  printf '@.claude/features/policy/coding-rules.md\n'
  printf '@.claude/features/policy/workflow-rules.md\n'
}

if [ "$WRITE_MODE" -eq 1 ]; then
  emit > "$TARGET_ROOT/CLAUDE.md"
  echo "generate-claude-md: wrote $TARGET_ROOT/CLAUDE.md" >&2
else
  emit
fi
