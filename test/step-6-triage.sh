#!/bin/bash
# Integration test: Step 6 — rabbit-triage.sh real impl; rabbit-vet.md archived.
# Non-interactive. All assertions are file-content and existence checks.
set -u

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null)}"
TRIAGE_SH="$REPO_ROOT/.claude/features/contract/scripts/rabbit-triage.sh"
VET_MD="$REPO_ROOT/.claude/agents/rabbit-vet.md"
VET_ARCHIVE="$REPO_ROOT/archive/2026-05-09-pre-redesign/agents/rabbit-vet.md"
TRIAGE_TEMPLATE="$REPO_ROOT/.claude/features/contract/templates/triage-template.md"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# 1. rabbit-triage.sh does NOT contain the word "stub"
if ! grep -qi "stub" "$TRIAGE_SH"; then
  ok "rabbit-triage.sh contains no 'stub' (real implementation)"
else
  ko "rabbit-triage.sh still contains 'stub'"
fi

# 2. rabbit-vet.md does NOT exist in .claude/agents/
if [ ! -f "$VET_MD" ]; then
  ok "rabbit-vet.md absent from .claude/agents/"
else
  ko "rabbit-vet.md still exists in .claude/agents/"
fi

# 3. rabbit-vet.md EXISTS in archive
if [ -f "$VET_ARCHIVE" ]; then
  ok "rabbit-vet.md present in archive/2026-05-09-pre-redesign/agents/"
else
  ko "rabbit-vet.md missing from archive/2026-05-09-pre-redesign/agents/"
fi

# 4. triage-template.md contains "TRIAGE:"
if grep -qF "TRIAGE:" "$TRIAGE_TEMPLATE"; then
  ok "triage-template.md contains 'TRIAGE:'"
else
  ko "triage-template.md missing 'TRIAGE:'"
fi

# 5. triage-template.md contains "classification"
if grep -qF "classification" "$TRIAGE_TEMPLATE"; then
  ok "triage-template.md contains 'classification'"
else
  ko "triage-template.md missing 'classification'"
fi

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
