#!/bin/bash
# End-to-end tests for list-bugs.sh.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FILE_BUG="$FEATURE_DIR/scripts/file-bug.sh"
STATUS="$FEATURE_DIR/scripts/bug-status.sh"
LIST="$FEATURE_DIR/scripts/list-bugs.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

export BUG_ROOT="$TMPROOT/bugs"
mkdir -p "$BUG_ROOT"

# Seed: 3 bugs, 2 open / 1 closed; 2 attached to 'feat-a' and 1 to 'feat-b'.
"$FILE_BUG" --name "2026-05-08-l1" --title "open A" --severity low --description d --related-feature feat-a >/dev/null
"$FILE_BUG" --name "2026-05-08-l2" --title "open B" --severity low --description d --related-feature feat-b >/dev/null
"$FILE_BUG" --name "2026-05-08-l3" --title "closed A" --severity low --description d --related-feature feat-a >/dev/null
"$STATUS" set "$BUG_ROOT/2026-05-08-l3" closed --note "x" >/dev/null

run() { "$LIST" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# l1: list all returns 3
l1() {
  run >/dev/null
  local n; n=$(jq 'length' "$TMPROOT/stdout" 2>/dev/null || echo "?")
  [ "$n" = "3" ] && ok "l1: list all returns 3" || ko "l1: n=$n out=$(cat "$TMPROOT/stdout")"
}

# l2: filter by --status open returns 2
l2() {
  run --status open >/dev/null
  local n; n=$(jq 'length' "$TMPROOT/stdout")
  [ "$n" = "2" ] && ok "l2: filter status=open returns 2" || ko "l2: n=$n"
}

# l3: filter by --status closed returns 1
l3() {
  run --status closed >/dev/null
  local n; n=$(jq 'length' "$TMPROOT/stdout")
  [ "$n" = "1" ] && ok "l3: filter status=closed returns 1" || ko "l3: n=$n"
}

# l4: filter by --feature feat-a returns 2
l4() {
  run --feature feat-a >/dev/null
  local n; n=$(jq 'length' "$TMPROOT/stdout")
  [ "$n" = "2" ] && ok "l4: filter feature=feat-a returns 2" || ko "l4: n=$n"
}

# l5: combine filters: status=open + feature=feat-a returns 1
l5() {
  run --status open --feature feat-a >/dev/null
  local n; n=$(jq 'length' "$TMPROOT/stdout")
  [ "$n" = "1" ] && ok "l5: status=open + feature=feat-a returns 1" || ko "l5: n=$n"
}

# l6: --text mode returns non-JSON output
l6() {
  run --text >/dev/null
  local out; out="$(cat "$TMPROOT/stdout")"
  echo "$out" | jq empty 2>/dev/null && { ko "l6: --text should NOT be JSON"; return; }
  echo "$out" | grep -q "2026-05-08-l1" \
    && ok "l6: --text lists bug names" \
    || ko "l6: missing bug name in output"
}

# l7: empty bug root returns []
l7() {
  rm -rf "$BUG_ROOT"; mkdir -p "$BUG_ROOT"
  run >/dev/null
  local out; out="$(cat "$TMPROOT/stdout")"
  [ "$out" = "[]" ] && ok "l7: empty bug root returns []" || ko "l7: out='$out'"
}

echo "running list-bugs tests against $LIST"
l1; l2; l3; l4; l5; l6; l7
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
