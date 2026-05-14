#!/bin/bash
# test-tdd-state-prune.sh — verify review/merged removed; spec-update added to tdd-context.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
TDD_STEP="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-step.sh"
TDD_CTX="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-context.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

make_feature() {
  local dir="$1" state="$2"
  mkdir -p "$dir"
  printf '{"name":"test-prune","tdd_state":"%s","version":"0.1.0","owner":"test","deprecation":{"criterion":"never"}}' "$state" > "$dir/feature.json"
}

# 1. review is not a valid state (even with --force)
make_feature "$TMPDIR_TEST/f1" test-green
bash "$TDD_STEP" transition "$TMPDIR_TEST/f1" review --force 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "review rejected even with --force" || fail "review should be invalid state"

# 2. merged is not a valid state (even with --force)
make_feature "$TMPDIR_TEST/f2" test-green
bash "$TDD_STEP" transition "$TMPDIR_TEST/f2" merged --force 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "merged rejected even with --force" || fail "merged should be invalid state"

# 3. next from test-green is deprecated
make_feature "$TMPDIR_TEST/f3" test-green
next=$(bash "$TDD_STEP" next "$TMPDIR_TEST/f3" 2>/dev/null)
[ "$next" = "deprecated" ] && ok "next from test-green is deprecated" || fail "next from test-green: expected 'deprecated', got '$next'"

# 4. normal forward chain still works: spec -> spec-update
make_feature "$TMPDIR_TEST/f4" spec
bash "$TDD_STEP" transition "$TMPDIR_TEST/f4" spec-update 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "spec -> spec-update still works" || fail "spec -> spec-update broken"

# 5. from spec, tdd-context.sh allowed_next_states = ["spec-update"]
make_feature "$TMPDIR_TEST/f5" spec
ctx=$(bash "$TDD_CTX" "$TMPDIR_TEST/f5" 2>/dev/null)
echo "$ctx" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['allowed_next_states'] == ['spec-update'], f'got {d[\"allowed_next_states\"]}'
" 2>/dev/null && ok "context: spec -> allowed_next = [spec-update]" || fail "context: spec allowed_next wrong"

# 6. from spec-update, tdd-context.sh allowed_next_states = ["test-red"]
make_feature "$TMPDIR_TEST/f6" spec-update
ctx=$(bash "$TDD_CTX" "$TMPDIR_TEST/f6" 2>/dev/null)
echo "$ctx" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['allowed_next_states'] == ['test-red'], f'got {d[\"allowed_next_states\"]}'
" 2>/dev/null && ok "context: spec-update -> allowed_next = [test-red]" || fail "context: spec-update allowed_next wrong"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
