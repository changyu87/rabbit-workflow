#!/usr/bin/env bash
# test-rule-files-content.sh — Spot-checks content of the four rule files.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check_phrase() {
  local file="$1"
  local phrase="$2"
  local path="$FEATURE_DIR/$file"
  if ! grep -q "$phrase" "$path"; then
    echo "FAIL: '$phrase' not found in $path" >&2
    exit 1
  fi
}

# spec-rules.md
check_phrase "spec-rules.md" "Tool-Choice Tier"
check_phrase "spec-rules.md" "Schemas and Contracts"
check_phrase "spec-rules.md" "Lifecycle and Ownership"

# coding-rules.md
check_phrase "coding-rules.md" "Think Before Coding"
check_phrase "coding-rules.md" "Simplicity First"
check_phrase "coding-rules.md" "Karpathy"

# philosophy.md
check_phrase "philosophy.md" "Machine First"
check_phrase "philosophy.md" "Bounded Scope"
check_phrase "philosophy.md" "Designed Deprecation"

check_phrase_absent() {
  local file="$1"
  local phrase="$2"
  local path="$FEATURE_DIR/$file"
  if grep -q "$phrase" "$path"; then
    echo "FAIL: '$phrase' should NOT be in $path but was found" >&2
    exit 1
  fi
}

check_first_heading() {
  local file="$1"
  local expected="$2"
  local path="$FEATURE_DIR/$file"
  local actual
  actual="$(grep -m1 '^#' "$path")"
  if [ "$actual" != "$expected" ]; then
    echo "FAIL: first heading in $path is '$actual', expected '$expected'" >&2
    exit 1
  fi
}

# CHANGE A — workflow-rules.md R6 updated text
# t_r6_new: workflow-rules.md R6 contains "generate-claude-md.sh"
check_phrase "workflow-rules.md" "generate-claude-md.sh"

# t_r6_old: workflow-rules.md R6 does NOT contain the old stale phrase
check_phrase_absent "workflow-rules.md" "no Agent-tool hook in Claude Code"

# CHANGE B — philosophy.md heading hierarchy fixed
# t_phil_h1: philosophy.md first non-empty line is "# Philosophy" (H1, not H2)
check_first_heading "philosophy.md" "# Philosophy"

# t_phil_no_h2: philosophy.md does NOT contain "## Philosophy" (the old H2)
check_phrase_absent "philosophy.md" "## Philosophy"

# t_phil_subsections: philosophy.md subsections use ## (H2), not ### (H3)
check_phrase "philosophy.md" "## 1. Machine First"

# t15 — metadata exception: workflow-rules.md Section 2 states metadata writes are exempt from TDD
REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
WFMD="$REPO_ROOT/.claude/features/policy/workflow-rules.md"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

if grep -qiE 'bug.fil|backlog.fil|schema.compliance|metadata.only' "$WFMD" 2>/dev/null; then
    ok 15 "workflow-rules.md documents metadata-write TDD exception"
else
    fail_t 15 "workflow-rules.md does not document the metadata-write exception"
fi

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
    exit 1
fi
