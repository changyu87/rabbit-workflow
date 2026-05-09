#!/bin/bash
# End-to-end test of the breeder agent definition file.
# Validates structure, required fields, and key system-prompt invariants.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
AGENT_FILE="$REPO_ROOT/.claude/agents/rabbit-breeder.md"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: file exists
[ -f "$AGENT_FILE" ] && ok "t1: $AGENT_FILE exists" || ko "t1: missing $AGENT_FILE"

# Bail on remaining tests if file missing
if [ ! -f "$AGENT_FILE" ]; then
  echo "summary: $PASS passed, $FAIL failed"; exit 1
fi

# Extract YAML frontmatter (between first two --- lines)
FRONT="$(awk '/^---$/{c++; next} c==1{print} c==2{exit}' "$AGENT_FILE")"
BODY="$(awk 'BEGIN{c=0} /^---$/{c++; next} c>=2{print}' "$AGENT_FILE")"

# t2: name field is rabbit-breeder
echo "$FRONT" | grep -qE '^name: *rabbit-breeder$' \
  && ok "t2: frontmatter name: rabbit-breeder" \
  || ko "t2: name field missing or wrong"

# t3: description present and non-trivial
DESC=$(echo "$FRONT" | sed -n 's/^description: *//p' | head -1)
[ -n "$DESC" ] && [ "${#DESC}" -gt 30 ] \
  && ok "t3: description present (${#DESC} chars)" \
  || ko "t3: description missing or too short"

# t4: tools list includes Write, Edit, Read, Bash
TOOLS_LINE=$(echo "$FRONT" | grep '^tools:' | head -1)
ALL_TOOLS_PRESENT=1
for t in Write Edit Read Bash; do
  echo "$TOOLS_LINE" | grep -qw "$t" || ALL_TOOLS_PRESENT=0
done
[ "$ALL_TOOLS_PRESENT" = "1" ] \
  && ok "t4: tools list includes Write, Edit, Read, Bash" \
  || ko "t4: tools missing one of Write/Edit/Read/Bash; line: $TOOLS_LINE"

# t5: body asserts scope-parameterized writer constraint (NOT hardcoded .claude/)
if echo "$BODY" | grep -qiE 'scope-parameterized|scope.*per dispatch|<SCOPE>|single explicit scope'; then
  ok "t5: body asserts scope-parameterized constraint"
else
  ko "t5: body lacks scope-parameterized framing"
fi

# t5b: body explicitly states .claude/ is NOT special in the work model
if echo "$BODY" | grep -qiE 'unified|same agent.*different scope|same code path|no.*rabbit dev mode|nothing.*special'; then
  ok "t5b: body asserts unified work model (.claude/ not special)"
else
  ko "t5b: body lacks unified work-model assertion"
fi

# t6: body references philosophy.md AND work-guide.md
echo "$BODY" | grep -q "philosophy.md" \
  && echo "$BODY" | grep -q "work-guide.md" \
  && ok "t6: body references philosophy.md and work-guide.md" \
  || ko "t6: body missing reference to philosophy.md or work-guide.md"

# t7: body explicitly refuses writes outside <SCOPE>
if echo "$BODY" | grep -qiE 'refuse.*outside.*scope|REJECTED: out-of-scope|outside.*<SCOPE>|out.*of.*scope'; then
  ok "t7: body refuses out-of-scope writes"
else
  ko "t7: body lacks refusal-of-out-of-scope-writes language"
fi

# t7b: body references the scope-guard hook / .rabbit-scope-active marker
if echo "$BODY" | grep -qE '\.rabbit-scope-active|scope-guard'; then
  ok "t7b: body references scope-guard hook / marker"
else
  ko "t7b: body lacks scope-guard hook reference"
fi

# t8: body references the feature-skeleton validator (writes to .claude/features/<name>/ should be validated)
if echo "$BODY" | grep -q "validate-feature.sh"; then
  ok "t8: body references validate-feature.sh for feature writes"
else
  ko "t8: body lacks reference to validate-feature.sh"
fi

# t9: body invokes tdd-context.sh or tdd-step.sh (breeder must respect TDD discipline)
if echo "$BODY" | grep -qE 'tdd-(context|step|drift)\.sh'; then
  ok "t9: body references TDD state-machine scripts"
else
  ko "t9: body lacks TDD state-machine integration"
fi

# t10: body mentions branch + PR discipline (no merging)
if echo "$BODY" | grep -qiE 'branch.*PR|PR.*branch|never.*merge|do not merge'; then
  ok "t10: body references branch/PR/no-merge discipline"
else
  ko "t10: body lacks branch/PR discipline"
fi

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
