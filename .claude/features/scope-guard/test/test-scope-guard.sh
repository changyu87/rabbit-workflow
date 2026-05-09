#!/bin/bash
# End-to-end test of scope-guard.sh hook.
# Pipes synthetic PreToolUse JSON into the hook against fixture trees and
# asserts allow/deny decisions.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOK="$FEATURE_DIR/../../hooks/scope-guard.sh"

# v2: fixtures that must be DENIED live inside the repo root so the
# repo-wide default-deny logic can reach them.
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
TMPROOT="$(mktemp -d "$REPO_ROOT/.sg-test-XXXXXX")"
# Fixtures that should be ALLOWED because they are outside the repo live in /tmp.
OUTSIDE_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT" "$OUTSIDE_ROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build a fake feature dir at $1.
mkfeat() {
  local d="$1"
  mkdir -p "$d/test"
  echo '{"name":"x","tdd_state":"spec"}' > "$d/feature.json"
}

# Run hook with given JSON, return rc and capture stderr.
run_hook() {
  local json="$1"
  echo "$json" | bash "$HOOK" 2>"$TMPROOT/err" >"$TMPROOT/out"
  echo $?
}

mk_write_json() {
  local path="$1"
  printf '{"tool_name":"Write","tool_input":{"file_path":"%s","content":"x"}}' "$path"
}
mk_edit_json() {
  local path="$1"
  printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$path"
}
mk_bash_json() {
  local cmd="$1"
  # JSON-escape the command (basic — assumes no quotes/newlines)
  printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$cmd"
}

# g1: Write to file outside the repo entirely -> allow
mkdir -p "$OUTSIDE_ROOT/g1"
echo "test" > "$OUTSIDE_ROOT/g1/random.txt"
rc=$(run_hook "$(mk_write_json "$OUTSIDE_ROOT/g1/foo.txt")")
[ "$rc" = "0" ] && ok "g1: Write outside repo root -> allow" \
  || ko "g1: rc=$rc err=$(cat "$TMPROOT/err")"

# g2: Write to file in feature dir without marker -> DENY
mkfeat "$TMPROOT/g2"
rc=$(run_hook "$(mk_write_json "$TMPROOT/g2/foo.md")")
[ "$rc" = "2" ] && grep -qi "scope-guard" "$TMPROOT/err" \
  && ok "g2: Write in feature dir without marker -> deny" \
  || ko "g2: rc=$rc err=$(cat "$TMPROOT/err")"

# g3: Write to file in feature dir WITH marker -> allow
mkfeat "$TMPROOT/g3"
touch "$TMPROOT/g3/.rabbit-scope-active"
rc=$(run_hook "$(mk_write_json "$TMPROOT/g3/foo.md")")
[ "$rc" = "0" ] && ok "g3: Write in feature dir with marker -> allow" \
  || ko "g3: rc=$rc err=$(cat "$TMPROOT/err")"

# g4: Edit to file in feature dir without marker -> DENY
mkfeat "$TMPROOT/g4"
rc=$(run_hook "$(mk_edit_json "$TMPROOT/g4/foo.md")")
[ "$rc" = "2" ] && ok "g4: Edit in feature dir without marker -> deny" \
  || ko "g4: rc=$rc"

# g5: Bash redirection > to feature dir without marker -> DENY
mkfeat "$TMPROOT/g5"
rc=$(run_hook "$(mk_bash_json "echo x > $TMPROOT/g5/file.txt")")
[ "$rc" = "2" ] && ok "g5: Bash > into feature dir without marker -> deny" \
  || ko "g5: rc=$rc err=$(cat "$TMPROOT/err")"

# g6: Bash redirection > to path outside repo -> allow
rc=$(run_hook "$(mk_bash_json "echo x > $OUTSIDE_ROOT/anywhere.txt")")
[ "$rc" = "0" ] && ok "g6: Bash > to path outside repo -> allow" \
  || ko "g6: rc=$rc err=$(cat "$TMPROOT/err")"

# g7: Write to .rabbit-scope-active itself -> allow (chicken-and-egg exempt)
mkfeat "$TMPROOT/g7"
rc=$(run_hook "$(mk_write_json "$TMPROOT/g7/.rabbit-scope-active")")
[ "$rc" = "0" ] && ok "g7: Write to marker file is exempt" \
  || ko "g7: rc=$rc err=$(cat "$TMPROOT/err")"

# g8: Bash rm of marker file -> allow (cleanup must work)
mkfeat "$TMPROOT/g8"
touch "$TMPROOT/g8/.rabbit-scope-active"
rc=$(run_hook "$(mk_bash_json "rm $TMPROOT/g8/.rabbit-scope-active")")
[ "$rc" = "0" ] && ok "g8: Bash rm of marker file is exempt" \
  || ko "g8: rc=$rc err=$(cat "$TMPROOT/err")"

# g9: Bash command that doesn't write (cat) -> allow
mkfeat "$TMPROOT/g9"
echo "x" > "$TMPROOT/g9/foo.md"  # bypassing hook for setup
rc=$(run_hook "$(mk_bash_json "cat $TMPROOT/g9/foo.md")")
[ "$rc" = "0" ] && ok "g9: Bash cat (read-only) -> allow" \
  || ko "g9: rc=$rc err=$(cat "$TMPROOT/err")"

# g10: walk-up: write to deep nested file in feature dir w/ marker at root -> allow
mkfeat "$TMPROOT/g10"
mkdir -p "$TMPROOT/g10/sub/deeper"
touch "$TMPROOT/g10/.rabbit-scope-active"
rc=$(run_hook "$(mk_write_json "$TMPROOT/g10/sub/deeper/foo.md")")
[ "$rc" = "0" ] && ok "g10: deep write under marker-bearing feature dir -> allow" \
  || ko "g10: rc=$rc err=$(cat "$TMPROOT/err")"

# g11: parallel scopes — markers in two distinct dirs; writes to either work
mkfeat "$TMPROOT/g11a"
mkfeat "$TMPROOT/g11b"
touch "$TMPROOT/g11a/.rabbit-scope-active"
touch "$TMPROOT/g11b/.rabbit-scope-active"
rc1=$(run_hook "$(mk_write_json "$TMPROOT/g11a/foo.md")")
rc2=$(run_hook "$(mk_write_json "$TMPROOT/g11b/foo.md")")
[ "$rc1" = "0" ] && [ "$rc2" = "0" ] \
  && ok "g11: parallel scope markers — both writes allowed" \
  || ko "g11: rc1=$rc1 rc2=$rc2"

# g12: Bash touch with marker present -> allow
mkfeat "$TMPROOT/g12"
touch "$TMPROOT/g12/.rabbit-scope-active"
rc=$(run_hook "$(mk_bash_json "touch $TMPROOT/g12/newfile.md")")
[ "$rc" = "0" ] && ok "g12: Bash touch in scope -> allow" \
  || ko "g12: rc=$rc err=$(cat "$TMPROOT/err")"

# g13: Bash touch in feature dir WITHOUT marker -> deny
mkfeat "$TMPROOT/g13"
rc=$(run_hook "$(mk_bash_json "touch $TMPROOT/g13/newfile.md")")
[ "$rc" = "2" ] && ok "g13: Bash touch out-of-scope -> deny" \
  || ko "g13: rc=$rc err=$(cat "$TMPROOT/err")"

# g14: Bash sed -i in feature dir without marker -> deny
mkfeat "$TMPROOT/g14"
echo "x" > "$TMPROOT/g14/foo.md"
rc=$(run_hook "$(mk_bash_json "sed -i s/x/y/ $TMPROOT/g14/foo.md")")
[ "$rc" = "2" ] && ok "g14: Bash sed -i out-of-scope -> deny" \
  || ko "g14: rc=$rc err=$(cat "$TMPROOT/err")"

# g15: Bash mv into feature dir without marker -> deny
mkfeat "$TMPROOT/g15"
echo "x" > "$TMPROOT/g15-src.txt"
rc=$(run_hook "$(mk_bash_json "mv $TMPROOT/g15-src.txt $TMPROOT/g15/landed.txt")")
[ "$rc" = "2" ] && ok "g15: Bash mv into scope dir without marker -> deny" \
  || ko "g15: rc=$rc err=$(cat "$TMPROOT/err")"

# g16: a tool we don't gate (e.g. Read) -> allow without check
rc=$(echo '{"tool_name":"Read","tool_input":{"file_path":"/anywhere"}}' \
     | bash "$HOOK"; echo $?)
[ "$rc" = "0" ] && ok "g16: ungated tool (Read) -> allow" \
  || ko "g16: rc=$rc"

# g17: v2 — write to a plain file at repo root (not a feature dir, not settings) is denied without marker
mkdir -p "$TMPROOT/g17plain"
rc=$(run_hook "$(mk_write_json "$TMPROOT/g17plain/readme.txt")")
[ "$rc" = "2" ] && ok "g17: v2 plain repo-root write without marker -> deny" \
  || ko "g17: rc=$rc err=$(cat "$TMPROOT/err")"

# g18: v2 — same write is allowed when a .rabbit-scope-active marker exists in an ancestor
mkdir -p "$TMPROOT/g18plain"
touch "$TMPROOT/g18plain/.rabbit-scope-active"
rc=$(run_hook "$(mk_write_json "$TMPROOT/g18plain/readme.txt")")
[ "$rc" = "0" ] && ok "g18: v2 plain repo-root write with ancestor marker -> allow" \
  || ko "g18: rc=$rc err=$(cat "$TMPROOT/err")"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
