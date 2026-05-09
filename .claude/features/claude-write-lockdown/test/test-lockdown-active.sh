#!/bin/bash
# Test check-lockdown-active.sh against fixture settings.json files.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK="$FEATURE_DIR/scripts/check-lockdown-active.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

run() { "$CHECK" "$1" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?; }

# t1: settings.json with both Write and Edit deny -> ok
cat > "$TMPROOT/ok.json" <<'EOF'
{
  "permissions": {
    "deny": [
      "Write(.claude/**)",
      "Edit(.claude/**)"
    ]
  }
}
EOF
rc=$(run "$TMPROOT/ok.json")
[ "$rc" = "0" ] && ok "t1: lockdown rules present -> ok" \
  || ko "t1: rc=$rc err=$(cat "$TMPROOT/err")"

# t2: settings.json with only Write deny -> fails
cat > "$TMPROOT/partial.json" <<'EOF'
{
  "permissions": {
    "deny": [
      "Write(.claude/**)"
    ]
  }
}
EOF
rc=$(run "$TMPROOT/partial.json")
[ "$rc" != "0" ] && grep -qi "Edit" "$TMPROOT/err" \
  && ok "t2: missing Edit deny -> fails (names Edit)" \
  || ko "t2: rc=$rc err=$(cat "$TMPROOT/err")"

# t3: settings.json with no permissions field -> fails
echo '{"env": {}}' > "$TMPROOT/none.json"
rc=$(run "$TMPROOT/none.json")
[ "$rc" != "0" ] && ok "t3: no permissions field -> fails" \
  || ko "t3: rc=$rc"

# t4: missing file -> error (rc 2)
rc=$(run "$TMPROOT/does-not-exist.json")
[ "$rc" != "0" ] && ok "t4: missing file -> errors" \
  || ko "t4: rc=$rc"

# t5: malformed JSON -> error
echo "not json {" > "$TMPROOT/bad.json"
rc=$(run "$TMPROOT/bad.json")
[ "$rc" != "0" ] && ok "t5: malformed JSON -> errors" \
  || ko "t5: rc=$rc"

# t6: extra deny rules don't break the check (Bash(rm) etc.)
cat > "$TMPROOT/plus.json" <<'EOF'
{
  "permissions": {
    "deny": [
      "Write(.claude/**)",
      "Edit(.claude/**)",
      "Bash(rm -rf *)"
    ]
  }
}
EOF
rc=$(run "$TMPROOT/plus.json")
[ "$rc" = "0" ] && ok "t6: extra deny rules tolerated" \
  || ko "t6: rc=$rc err=$(cat "$TMPROOT/err")"

# t7: with no path arg, defaults to .claude/settings.json (which AFTER this PR has the rules)
# Run from the repo root so the default path resolves correctly.
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
( cd "$REPO_ROOT" && "$CHECK" 2>"$TMPROOT/err" >"$TMPROOT/out" )
rc=$?
if [ "$rc" = "0" ]; then
  ok "t7: shared .claude/settings.json has lockdown rules"
else
  ko "t7: shared settings.json missing lockdown rules; err=$(cat "$TMPROOT/err")"
fi

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
