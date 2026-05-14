#!/bin/bash
# test-tdd-report-gate.sh — verify --tdd-report flag and updated R7 gate
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-bug/scripts/bug-status.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
BUG_DIR="$TMPDIR_TEST/RABBIT-BUG-99"
mkdir -p "$BUG_DIR"

reset_bug() {
  printf '{"id":"RABBIT-BUG-99","title":"test bug","severity":"low","status":"open","history":[]}' \
    > "$BUG_DIR/bug.json"
}

reset_bug

# 1. close fails without vet-triage.json (baseline R7 still works)
bash "$SCRIPT" set "$BUG_DIR" closed --reason "fix" 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "close fails without vet-triage.json" || fail "should fail without vet-triage.json"

# 2. close fails with vet-triage.json but no --tdd-report
touch "$BUG_DIR/vet-triage.json"
bash "$SCRIPT" set "$BUG_DIR" closed --reason "fix" 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "close fails without --tdd-report" || fail "should fail without --tdd-report"

# 3. close succeeds with vet-triage.json + --tdd-report
cat > "$TMPDIR_TEST/tdd-report.json" <<'JSON'
{"schema_version":"1.0.0","feature":"test","test_result":"pass","tdd_state":"test-green",
 "impl_summary":"fixed","spec_compliance":"pass","test_gap_analysis":"none","impl_commit":"abc123"}
JSON
bash "$SCRIPT" set "$BUG_DIR" closed \
  --reason "TDD cycle complete" \
  --tdd-report "$TMPDIR_TEST/tdd-report.json" \
  --fix-commits "abc123" 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "close succeeds with vet-triage.json + --tdd-report" || fail "close failed: exit $code"

# 4. bug.json history contains tdd_report field
has_rpt=$(python3 -c "
import json
h = json.load(open('$BUG_DIR/bug.json'))['history']
print('yes' if h and 'tdd_report' in h[-1] else 'no')
" 2>/dev/null)
[ "$has_rpt" = "yes" ] && ok "bug.json history has tdd_report field" || fail "bug.json missing tdd_report in history"

# 5. tdd-gap.json is NOT required (old requirement removed)
reset_bug
touch "$BUG_DIR/vet-triage.json"
rm -f "$BUG_DIR/tdd-gap.json"
bash "$SCRIPT" set "$BUG_DIR" closed \
  --reason "fix" \
  --tdd-report "$TMPDIR_TEST/tdd-report.json" \
  --fix-commits "abc123" 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "tdd-gap.json not required" || fail "should not require tdd-gap.json: exit $code"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
