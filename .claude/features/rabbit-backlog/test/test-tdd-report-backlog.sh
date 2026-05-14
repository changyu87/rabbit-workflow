#!/bin/bash
# test-tdd-report-backlog.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-backlog/scripts/backlog-item-status.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
ITEM_DIR="$TMPDIR_TEST/RABBIT-BACKLOG-99"
mkdir -p "$ITEM_DIR"

cat > "$ITEM_DIR/item.json" <<'JSON'
{"id":"RABBIT-BACKLOG-99","title":"test item","priority":"medium","status":"in-progress","history":[]}
JSON
cat > "$TMPDIR_TEST/tdd-report.json" <<'JSON'
{"schema_version":"1.0.0","feature":"test","test_result":"pass","tdd_state":"test-green",
 "impl_summary":"done","spec_compliance":"pass","test_gap_analysis":"none","impl_commit":"abc123"}
JSON

# 1. implemented with --tdd-report succeeds
bash "$SCRIPT" set "$ITEM_DIR" implemented \
  --reason "TDD complete" \
  --tdd-report "$TMPDIR_TEST/tdd-report.json" \
  --fix-commits "abc123" 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "implemented with --tdd-report succeeds" || fail "implemented failed: $code"

# 2. item.json history has tdd_report field
has_rpt=$(python3 -c "
import json
h = json.load(open('$ITEM_DIR/item.json'))['history']
print('yes' if h and 'tdd_report' in h[-1] else 'no')
" 2>/dev/null)
[ "$has_rpt" = "yes" ] && ok "history has tdd_report field" || fail "missing tdd_report in history"

# 3. item.json history has fix_commits field
has_fc=$(python3 -c "
import json
h = json.load(open('$ITEM_DIR/item.json'))['history']
print('yes' if h and 'fix_commits' in h[-1] else 'no')
" 2>/dev/null)
[ "$has_fc" = "yes" ] && ok "history has fix_commits field" || fail "missing fix_commits in history"

# 4. status is now implemented
status=$(bash "$SCRIPT" get "$ITEM_DIR" 2>/dev/null)
[ "$status" = "implemented" ] && ok "status is implemented" || fail "status: got '$status'"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
