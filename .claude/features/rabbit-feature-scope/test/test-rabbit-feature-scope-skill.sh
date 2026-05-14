#!/bin/bash
# test-rabbit-feature-scope-skill.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL="$REPO_ROOT/.claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md"
DEPLOYED="$REPO_ROOT/.claude/skills/rabbit-feature-scope/SKILL.md"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

[ -f "$SKILL" ] || { echo "FAIL: source SKILL.md missing"; exit 1; }
[ -f "$DEPLOYED" ] || { echo "FAIL: deployed SKILL.md missing"; exit 1; }

for phrase in \
  "resolve-scope.sh" \
  '"features"' \
  '"rationale"' \
  "default model" \
  "single line" \
  "find-feature.sh"
do
  grep -q "$phrase" "$SKILL" \
    && ok "source SKILL.md contains: $phrase" \
    || fail "source SKILL.md missing: $phrase"
done

# Deployed copy matches source
diff "$SKILL" "$DEPLOYED" >/dev/null 2>&1 \
  && ok "deployed copy matches source" \
  || fail "deployed copy differs from source"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
