#!/bin/bash
# test-rabbit-bug-skill-v2.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL="$REPO_ROOT/.claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md"
DEPLOYED="$REPO_ROOT/.claude/skills/rabbit-bug/SKILL.md"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

[ -f "$SKILL" ] || { echo "FAIL: source SKILL.md missing"; exit 1; }

for phrase in \
  "Filing protocol" \
  "Working protocol" \
  "eval subagent" \
  "rabbit-feature-touch" \
  "B/B mode" \
  "tdd-report.json" \
  "filing/RABBIT-BUG" \
  "auto-merge" \
  "status: success|failed" \
  "vet-triage.json"
do
  grep -qiE "$phrase" "$SKILL" \
    && ok "SKILL.md contains: $phrase" \
    || fail "SKILL.md missing: $phrase"
done

diff "$SKILL" "$DEPLOYED" >/dev/null 2>&1 \
  && ok "deployed copy matches source" \
  || fail "deployed copy differs from source"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
