#!/usr/bin/env bash
# test-backlog-skill.sh
# t1: skills/rabbit-backlog/SKILL.md exists
# t2: SKILL.md has name and description frontmatter fields
# t3: feature.json surface.skills contains "rabbit-backlog"
# t4: SKILL.md has a list-backlog.sh section header
# t5: SKILL.md has a usage block for list-backlog.sh (all flags present)
# t6: SKILL.md has a parameters table for list-backlog.sh
# t7: SKILL.md has example invocations for list-backlog.sh (no-args, --text, --status, --feature)

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_MD="$FEATURE_DIR/skills/rabbit-backlog/SKILL.md"

pass=0; fail=0
ok()     { echo "  PASS t$1: $2"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail + 1)); }

echo "test-backlog-skill.sh"

T1_LABEL="t1: skills/rabbit-backlog/SKILL.md exists"
if [ -f "$SKILL_MD" ]; then ok 1 "$T1_LABEL"; else fail_t 1 "$T1_LABEL"; fi

T2_LABEL="t2: SKILL.md has name and description frontmatter"
if [ -f "$SKILL_MD" ] && grep -q '^name:' "$SKILL_MD" && grep -q '^description:' "$SKILL_MD"; then
  ok 2 "$T2_LABEL"
else
  fail_t 2 "$T2_LABEL"
fi

T3_LABEL="t3: feature.json surface.skills is [] (skills managed via build-contract.json)"
FJ="$FEATURE_DIR/feature.json"
if python3 -c "
import json, sys
d = json.load(open('$FJ'))
skills = d.get('surface', {}).get('skills', None)
assert isinstance(skills, list) and len(skills) == 0, f'expected [], got {skills!r}'
" 2>/dev/null; then
  ok 3 "$T3_LABEL"
else
  fail_t 3 "$T3_LABEL"
fi

T4_LABEL="t4: SKILL.md has a list-backlog.sh section header"
if [ -f "$SKILL_MD" ] && grep -q 'list-backlog\.sh' "$SKILL_MD"; then
  ok 4 "$T4_LABEL"
else
  fail_t 4 "$T4_LABEL"
fi

T5_LABEL="t5: SKILL.md usage block for list-backlog.sh documents all flags (--status, --feature, --text, -h/--help)"
if [ -f "$SKILL_MD" ] && \
   grep -q '\-\-status' "$SKILL_MD" && \
   grep -q '\-\-feature' "$SKILL_MD" && \
   grep -q '\-\-text' "$SKILL_MD" && \
   grep -q '\-h\|--help\|--help' "$SKILL_MD"; then
  ok 5 "$T5_LABEL"
else
  fail_t 5 "$T5_LABEL"
fi

T6_LABEL="t6: SKILL.md has a parameters table for list-backlog.sh (| Flag | pattern)"
if [ -f "$SKILL_MD" ] && grep -qE '^\| (Flag|\*\(no args\)\*|`--status`|`--feature`|`--text`)' "$SKILL_MD"; then
  ok 6 "$T6_LABEL"
else
  fail_t 6 "$T6_LABEL"
fi

T7_LABEL="t7: SKILL.md has example invocations for list-backlog.sh (no-args, --text, --status, --feature)"
EXAMPLES_OK=1
if [ -f "$SKILL_MD" ]; then
  # Must have at least one bare list-backlog.sh call (no-args example)
  grep -q 'list-backlog\.sh$\|list-backlog\.sh #' "$SKILL_MD" || EXAMPLES_OK=0
  # Must have --text example
  grep -q 'list-backlog\.sh.*--text\|--text.*list-backlog\.sh' "$SKILL_MD" || EXAMPLES_OK=0
  # Must have --status example
  grep -q 'list-backlog\.sh.*--status\|--status.*list-backlog\.sh' "$SKILL_MD" || EXAMPLES_OK=0
  # Must have --feature example
  grep -q 'list-backlog\.sh.*--feature\|--feature.*list-backlog\.sh' "$SKILL_MD" || EXAMPLES_OK=0
else
  EXAMPLES_OK=0
fi
if [ "$EXAMPLES_OK" -eq 1 ]; then
  ok 7 "$T7_LABEL"
else
  fail_t 7 "$T7_LABEL"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
