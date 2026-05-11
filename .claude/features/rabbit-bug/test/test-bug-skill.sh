#!/usr/bin/env bash
# test-bug-skill.sh
# t1: skills/rabbit-bug/SKILL.md exists
# t2: SKILL.md has name and description frontmatter fields
# t3: feature.json surface.skills contains "rabbit-bug"

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_MD="$FEATURE_DIR/skills/rabbit-bug/SKILL.md"

pass=0; fail=0
ok()     { echo "  PASS t$1: $2"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail + 1)); }

echo "test-bug-skill.sh"

T1_LABEL="t1: skills/rabbit-bug/SKILL.md exists"
if [ -f "$SKILL_MD" ]; then ok 1 "$T1_LABEL"; else fail_t 1 "$T1_LABEL"; fi

T2_LABEL="t2: SKILL.md has name and description frontmatter"
if [ -f "$SKILL_MD" ] && grep -q '^name:' "$SKILL_MD" && grep -q '^description:' "$SKILL_MD"; then
  ok 2 "$T2_LABEL"
else
  fail_t 2 "$T2_LABEL"
fi

T3_LABEL="t3: feature.json surface.skills includes 'rabbit-bug'"
FJ="$FEATURE_DIR/feature.json"
if python3 -c "
import json, sys
d = json.load(open('$FJ'))
assert 'rabbit-bug' in d.get('surface', {}).get('skills', []), 'not found'
" 2>/dev/null; then
  ok 3 "$T3_LABEL"
else
  fail_t 3 "$T3_LABEL"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
