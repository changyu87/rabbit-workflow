#!/bin/bash
# End-to-end test of policy-block.sh.
# Verifies the canonical policy block contains philosophy + work-guide content,
# carries hard-command framing tokens, supports --include for related files,
# and errors clearly on missing includes.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT="$FEATURE_DIR/scripts/policy-block.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

run() { "$SCRIPT" "$@" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?; }

# p1: script outputs non-empty
rc=$(run)
size=$(wc -c < "$TMPROOT/out")
[ "$rc" = "0" ] && [ "$size" -gt 100 ] \
  && ok "p1: script outputs non-empty ($size bytes)" \
  || ko "p1: rc=$rc size=$size err=$(cat "$TMPROOT/err")"

# p2: output contains all three philosophy.md principle names
ALL=1
for principle in "Machine First" "Bounded Scope" "Designed Deprecation"; do
  grep -q "$principle" "$TMPROOT/out" || ALL=0
done
[ "$ALL" = "1" ] && ok "p2: contains all three philosophy principles" \
  || ko "p2: missing one of Machine First / Bounded Scope / Designed Deprecation"

# p3: output contains all three work-guide.md section titles
ALL=1
for section in "Tool-Choice Tier" "Schemas and Contracts" "Lifecycle and Ownership"; do
  grep -q "$section" "$TMPROOT/out" || ALL=0
done
[ "$ALL" = "1" ] && ok "p3: contains all three work-guide section titles" \
  || ko "p3: missing one of Tool-Choice Tier / Schemas and Contracts / Lifecycle and Ownership"

# p4: hard-command framing tokens present
COUNT=0
for token in "MANDATORY" "NOT optional" "STOP" "constitution"; do
  grep -q "$token" "$TMPROOT/out" && COUNT=$((COUNT+1))
done
[ "$COUNT" -ge 3 ] && ok "p4: hard-command framing present ($COUNT/4 tokens)" \
  || ko "p4: weak framing ($COUNT/4 tokens; need at least 3)"

# p5: --include adds the file's content with a divider header
echo "MARKER_FROM_INCLUDE_FILE_FOR_TEST" > "$TMPROOT/extra.md"
run --include "$TMPROOT/extra.md"
grep -q "MARKER_FROM_INCLUDE_FILE_FOR_TEST" "$TMPROOT/out" \
  && grep -q "extra.md" "$TMPROOT/out" \
  && ok "p5: --include inserts file content + filename divider" \
  || ko "p5: --include did not insert content; out tail: $(tail -5 "$TMPROOT/out")"

# p6: missing --include path errors with clear message
rc=$(run --include "$TMPROOT/does-not-exist.md")
[ "$rc" != "0" ] && grep -qiE "include|exist|not found|missing" "$TMPROOT/err" \
  && ok "p6: missing --include path errors clearly" \
  || ko "p6: rc=$rc err=$(cat "$TMPROOT/err")"

# p7: output is plain text (no NUL bytes / binary garbage)
run
if file "$TMPROOT/out" | grep -qE "ASCII text|UTF-8 Unicode text"; then
  ok "p7: output is plain text"
elif ! tr -d '\0' < "$TMPROOT/out" | cmp -s - "$TMPROOT/out"; then
  ko "p7: output contains NUL bytes"
else
  ok "p7: output is plain text (file: $(file "$TMPROOT/out"))"
fi

# p8: multiple --include flags work (composable)
echo "MARKER_A" > "$TMPROOT/a.md"
echo "MARKER_B" > "$TMPROOT/b.md"
run --include "$TMPROOT/a.md" --include "$TMPROOT/b.md"
grep -q "MARKER_A" "$TMPROOT/out" && grep -q "MARKER_B" "$TMPROOT/out" \
  && ok "p8: multiple --include flags compose" \
  || ko "p8: only one --include applied"

# p9: output starts with the hard banner (visual delimiter)
first_line=$(head -1 "$TMPROOT/out")
echo "$first_line" | grep -qE "═══|####|MANDATORY" \
  && ok "p9: output opens with a visual hard banner" \
  || ko "p9: opening line lacks banner: '$first_line'"

# p10: output ends with the closing banner
last_lines=$(tail -3 "$TMPROOT/out")
echo "$last_lines" | grep -qE "═══|####|END POLICY|proceed" \
  && ok "p10: output closes with a banner / END marker" \
  || ko "p10: tail lacks closing banner"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
