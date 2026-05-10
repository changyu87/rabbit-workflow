#!/usr/bin/env bash
# test-oneliner-comment.sh
# Verifies that CLAUDE.md begins with a workflow identity comment (one-liner)
# that appears BEFORE the first @-import line and covers:
#   (1) dispatcher / main-session identity
#   (2) what it helps with (dispatching, bugs, triage, scaffolding)
#   (3) full-feature-oriented + full TDD behavioral traits

set -euo pipefail

CLAUDE_MD="$(dirname "$0")/../CLAUDE.md"

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "PASS: $1"; }

# ── helper: find the line number of the first @-import ──────────────────────
first_import_line() {
  grep -n '^@' "$CLAUDE_MD" | head -1 | cut -d: -f1
}

# ── Test 1: file must contain a comment/paragraph before the first @-import ──
import_line=$(first_import_line)
[[ -z "$import_line" ]] && fail "No @-import line found in CLAUDE.md"

# Collect all lines before the first @-import
preamble=$(head -n "$((import_line - 1))" "$CLAUDE_MD")

[[ -z "$preamble" ]] && fail "No content before the first @-import line — one-liner comment is missing"

# ── Test 2: preamble must mention dispatcher / main-session identity ──────────
echo "$preamble" | grep -qi "dispatch" \
  || fail "Preamble does not mention 'dispatch' (identity trait missing)"

# ── Test 3: preamble must mention at least one help capability ────────────────
echo "$preamble" | grep -qiE "bug|triage|scaffold|feature" \
  || fail "Preamble does not mention capabilities (bug/triage/scaffold/feature)"

# ── Test 4: preamble must mention full-feature-oriented trait ─────────────────
echo "$preamble" | grep -qiE "feature.oriented|full.feature|feature oriented" \
  || fail "Preamble does not mention 'full feature oriented' trait"

# ── Test 5: preamble must mention TDD trait ───────────────────────────────────
echo "$preamble" | grep -qiE "TDD|test.driven" \
  || fail "Preamble does not mention TDD trait"

pass "All checks passed — CLAUDE.md has a valid workflow identity comment before @-imports"
exit 0
