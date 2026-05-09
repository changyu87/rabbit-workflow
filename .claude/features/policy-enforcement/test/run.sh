#!/bin/bash
# End-to-end test of the policy-enforcement feature: verify the policy anchor
# files exist and contain the load-bearing sections that philosophy and
# work-guide must always carry.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
PHIL="$REPO_ROOT/.claude/philosophy.md"
GUIDE="$REPO_ROOT/.claude/work-guide.md"
ANCHOR="$REPO_ROOT/CLAUDE.md"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: philosophy.md exists
[ -f "$PHIL" ] && ok "t1: philosophy.md exists" || ko "t1: missing $PHIL"

# t2: work-guide.md exists
[ -f "$GUIDE" ] && ok "t2: work-guide.md exists" || ko "t2: missing $GUIDE"

# t3: CLAUDE.md (policy anchor) exists at repo root
[ -f "$ANCHOR" ] && ok "t3: CLAUDE.md exists" || ko "t3: missing $ANCHOR"

# Bail if any of the three are missing
[ ! -f "$PHIL" ] || [ ! -f "$GUIDE" ] || [ ! -f "$ANCHOR" ] && {
  echo "summary: $PASS passed, $FAIL failed"; exit 1; }

# t4: philosophy.md contains the three load-bearing principles
for principle in "Machine First" "Bounded Scope" "Designed Deprecation"; do
  if grep -q "$principle" "$PHIL"; then
    ok "t4.$principle: philosophy.md contains '$principle'"
  else
    ko "t4.$principle: missing principle '$principle' in philosophy.md"
  fi
done

# t5: work-guide.md contains its load-bearing sections
for section in "Tool-Choice Tier" "Schemas and Contracts" "Lifecycle and Ownership"; do
  if grep -q "$section" "$GUIDE"; then
    ok "t5.$section: work-guide.md contains '$section'"
  else
    ko "t5.$section: missing section '$section' in work-guide.md"
  fi
done

# t6: CLAUDE.md @-imports both files
if grep -qE '^@\.?/\.claude/philosophy\.md' "$ANCHOR" \
   && grep -qE '^@\.?/\.claude/work-guide\.md' "$ANCHOR"; then
  ok "t6: CLAUDE.md @-imports both philosophy.md and work-guide.md"
else
  ko "t6: CLAUDE.md is missing one or both @-imports"
fi

# t7: philosophy.md non-trivial size (sanity, > 500 bytes)
size=$(wc -c < "$PHIL")
[ "$size" -gt 500 ] && ok "t7: philosophy.md size sanity ($size bytes > 500)" \
  || ko "t7: philosophy.md too small ($size bytes)"

# t8: work-guide.md non-trivial size (> 1000 bytes)
size=$(wc -c < "$GUIDE")
[ "$size" -gt 1000 ] && ok "t8: work-guide.md size sanity ($size bytes > 1000)" \
  || ko "t8: work-guide.md too small ($size bytes)"

# t9: CLAUDE.md size sanity (> 100 bytes; small but non-empty)
size=$(wc -c < "$ANCHOR")
[ "$size" -gt 100 ] && ok "t9: CLAUDE.md size sanity ($size bytes > 100)" \
  || ko "t9: CLAUDE.md too small ($size bytes)"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
