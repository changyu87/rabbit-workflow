#!/bin/bash
# Static validation of the bug-handler agent definition file.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
AGENT_FILE="$REPO_ROOT/.claude/agents/rabbit-bug-handler.md"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

[ -f "$AGENT_FILE" ] && ok "t1: $AGENT_FILE exists" || { ko "t1: missing $AGENT_FILE"; echo "summary: $PASS passed, $FAIL failed"; exit 1; }

FRONT="$(awk '/^---$/{c++; next} c==1{print} c==2{exit}' "$AGENT_FILE")"
BODY="$(awk 'BEGIN{c=0} /^---$/{c++; next} c>=2{print}' "$AGENT_FILE")"

# t2: name = rabbit-bug-handler
echo "$FRONT" | grep -qE '^name: *rabbit-bug-handler$' \
  && ok "t2: frontmatter name: rabbit-bug-handler" \
  || ko "t2: name field missing or wrong"

# t3: description present and substantive
DESC=$(echo "$FRONT" | sed -n 's/^description: *//p' | head -1)
[ -n "$DESC" ] && [ "${#DESC}" -gt 30 ] \
  && ok "t3: description present (${#DESC} chars)" \
  || ko "t3: description missing or too short"

# t4: tools list includes Read, Bash, Glob, Grep
TOOLS_LINE=$(echo "$FRONT" | grep '^tools:' | head -1)
ALL=1
for t in Read Bash Glob Grep; do
  echo "$TOOLS_LINE" | grep -qw "$t" || ALL=0
done
[ "$ALL" = "1" ] \
  && ok "t4: tools include Read/Bash/Glob/Grep" \
  || ko "t4: tools missing one; line: $TOOLS_LINE"

# t5: tools list does NOT include Write or Edit (bug-handler is read-only)
if echo "$TOOLS_LINE" | grep -qw "Write" || echo "$TOOLS_LINE" | grep -qw "Edit"; then
  ko "t5: tools list MUST NOT include Write or Edit (bug-handler is read-only); line: $TOOLS_LINE"
else
  ok "t5: tools list excludes Write and Edit (read-only enforced)"
fi

# t6: body explains triage role
echo "$BODY" | grep -qiE 'triage|classif' \
  && ok "t6: body explains triage role" \
  || ko "t6: body lacks triage language"

# t7: body references bug-filing scripts
echo "$BODY" | grep -qE 'bug-status\.sh|file-bug\.sh|list-bugs\.sh' \
  && ok "t7: body references bug-filing scripts" \
  || ko "t7: body missing bug-filing script refs"

# t8: body specifies the TRIAGE output format
echo "$BODY" | grep -q "TRIAGE:" \
  && ok "t8: body specifies TRIAGE output format" \
  || ko "t8: body missing TRIAGE: marker"

# t9: body explicitly refuses to write
if echo "$BODY" | grep -qiE 'do not write|never write|read-only|no writes|will not write'; then
  ok "t9: body refuses to write (read-only discipline)"
else
  ko "t9: body lacks read-only assertion"
fi

# t10: body references handing off to breeder or caller for actions
if echo "$BODY" | grep -qiE 'breeder|hand off|handoff|caller acts|caller dispatches'; then
  ok "t10: body references handoff to breeder/caller for actions"
else
  ko "t10: body lacks handoff language"
fi

# t11: body references test-gap classification (bug that exposes missing test coverage)
if echo "$BODY" | grep -qiE 'test[ -]gap|missing test|test coverage|untested'; then
  ok "t11: body addresses test-gap classification"
else
  ko "t11: body lacks test-gap concept"
fi

# t12: body references philosophy/work-guide alignment
echo "$BODY" | grep -q "philosophy.md" && echo "$BODY" | grep -q "work-guide.md" \
  && ok "t12: body references philosophy.md and work-guide.md" \
  || ko "t12: body lacks philosophy/work-guide refs"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
