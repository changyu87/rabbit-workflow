#!/bin/bash
# End-to-end test of check-naming.sh.
# The check scans .claude/commands, .claude/agents, .claude/skills under a
# given root and verifies every artifact name (file basename without .md, or
# directory name for skills) starts with 'rabbit-'.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK="$FEATURE_DIR/scripts/check-naming.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# All cases use $TMPROOT/case-N/ as a fake repo root. The check is run with
# that path as the positional arg.
mkfix() {
  local d="$1"
  mkdir -p "$d/.claude/commands" "$d/.claude/agents" "$d/.claude/skills"
}

run() { "$CHECK" "$1" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?; }

# t1: empty .claude tree -> ok (no artifacts to check)
d="$TMPROOT/c1"; mkfix "$d"
rc=$(run "$d")
[ "$rc" = "0" ] && ok "t1: empty tree -> ok" || ko "t1: rc=$rc err=$(cat "$TMPROOT/err")"

# t2: all rabbit- prefixed -> ok
d="$TMPROOT/c2"; mkfix "$d"
echo > "$d/.claude/commands/rabbit-foo.md"
echo > "$d/.claude/agents/rabbit-bar.md"
mkdir -p "$d/.claude/skills/rabbit-baz"
rc=$(run "$d")
[ "$rc" = "0" ] && ok "t2: all rabbit- prefixed -> ok" \
  || ko "t2: rc=$rc err=$(cat "$TMPROOT/err")"

# t3: rwf- prefixed command -> fails (and names the file)
d="$TMPROOT/c3"; mkfix "$d"
echo > "$d/.claude/commands/rwf-refresh.md"
rc=$(run "$d")
[ "$rc" != "0" ] && grep -q "rwf-refresh" "$TMPROOT/err" \
  && ok "t3: rwf- command -> fails (names file)" \
  || ko "t3: rc=$rc err=$(cat "$TMPROOT/err")"

# t4: nude command (no prefix) -> fails
d="$TMPROOT/c4"; mkfix "$d"
echo > "$d/.claude/commands/refresh.md"
rc=$(run "$d")
[ "$rc" != "0" ] && grep -q "refresh.md" "$TMPROOT/err" \
  && ok "t4: nude command -> fails" \
  || ko "t4: rc=$rc err=$(cat "$TMPROOT/err")"

# t5: nude agent -> fails
d="$TMPROOT/c5"; mkfix "$d"
echo > "$d/.claude/agents/breeder.md"
rc=$(run "$d")
[ "$rc" != "0" ] && grep -q "breeder.md" "$TMPROOT/err" \
  && ok "t5: nude agent -> fails" \
  || ko "t5: rc=$rc err=$(cat "$TMPROOT/err")"

# t6: nude skill (directory) -> fails
d="$TMPROOT/c6"; mkfix "$d"
mkdir -p "$d/.claude/skills/sneaky-skill"
rc=$(run "$d")
[ "$rc" != "0" ] && grep -q "sneaky-skill" "$TMPROOT/err" \
  && ok "t6: nude skill -> fails" \
  || ko "t6: rc=$rc err=$(cat "$TMPROOT/err")"

# t7: mix - one ok, one bad -> fails and names only the bad
d="$TMPROOT/c7"; mkfix "$d"
echo > "$d/.claude/commands/rabbit-good.md"
echo > "$d/.claude/commands/rwf-bad.md"
rc=$(run "$d")
[ "$rc" != "0" ] && grep -q "rwf-bad" "$TMPROOT/err" \
  && ! grep -q "rabbit-good.*VIOLATION\|VIOLATION.*rabbit-good" "$TMPROOT/err" \
  && ok "t7: mix - only the bad named" \
  || ko "t7: rc=$rc err=$(cat "$TMPROOT/err")"

# t8: missing .claude dir entirely -> ok (vacuous)
d="$TMPROOT/c8"
mkdir -p "$d"
rc=$(run "$d")
[ "$rc" = "0" ] && ok "t8: no .claude dir -> ok (vacuous)" \
  || ko "t8: rc=$rc err=$(cat "$TMPROOT/err")"

# t9: README.md or other non-artifact files in commands dir are ignored
d="$TMPROOT/c9"; mkfix "$d"
echo > "$d/.claude/commands/README.md"
echo > "$d/.claude/commands/rabbit-cmd.md"
rc=$(run "$d")
[ "$rc" = "0" ] && ok "t9: README.md is ignored (not an artifact name)" \
  || ko "t9: rc=$rc err=$(cat "$TMPROOT/err")"

# t10: count of violations reported on FAIL line
d="$TMPROOT/c10"; mkfix "$d"
echo > "$d/.claude/commands/rwf-a.md"
echo > "$d/.claude/agents/rwf-b.md"
echo > "$d/.claude/agents/c.md"
rc=$(run "$d")
fail_line=$(grep -i '^FAIL:' "$TMPROOT/err" | tail -1)
[ "$rc" != "0" ] && echo "$fail_line" | grep -q "3" \
  && ok "t10: FAIL line reports count (3)" \
  || ko "t10: rc=$rc fail_line='$fail_line'"

# t11: real repo (where this test lives) - check shouldn't false-positive
# Run against the actual repo root. After the rename portion of this PR,
# all commands/agents on this branch should be rabbit-prefixed and no rwf-
# prefixed files should remain outside docs/.
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
rc=$("$CHECK" "$REPO_ROOT" 2>"$TMPROOT/err" >"$TMPROOT/out"; echo $?)
[ "$rc" = "0" ] && ok "t11: repo's own .claude/ passes naming check" \
  || ko "t11: rc=$rc err=$(cat "$TMPROOT/err")"

# t12: rwf-prefixed file anywhere in .claude/ (e.g. hooks/) -> fails
d="$TMPROOT/c12"; mkfix "$d"
mkdir -p "$d/.claude/hooks"
echo > "$d/.claude/hooks/rwf-refresh.sh"
rc=$(run "$d")
[ "$rc" != "0" ] && grep -q "rwf-refresh.sh" "$TMPROOT/err" \
  && ok "t12: rwf-prefixed hook script -> fails" \
  || ko "t12: rc=$rc err=$(cat "$TMPROOT/err")"

# t13: rbt-prefixed file is allowed (internal naming)
d="$TMPROOT/c13"; mkfix "$d"
mkdir -p "$d/.claude/hooks"
echo > "$d/.claude/hooks/rbt-refresh.sh"
rc=$(run "$d")
[ "$rc" = "0" ] && ok "t13: rbt-prefixed hook script -> ok" \
  || ko "t13: rc=$rc err=$(cat "$TMPROOT/err")"

# t14: rwf- file inside .claude/docs/ is allowed (historical)
d="$TMPROOT/c14"; mkfix "$d"
mkdir -p "$d/.claude/docs/plans"
echo > "$d/.claude/docs/plans/rwf-historical-plan.md"
rc=$(run "$d")
[ "$rc" = "0" ] && ok "t14: rwf- inside docs/ is tolerated (historical)" \
  || ko "t14: rc=$rc err=$(cat "$TMPROOT/err")"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
