#!/usr/bin/env bash
# test-scope-guard-allowlist.sh
# Tests that scope-guard.sh includes .rabbit-scope-override in its allowlist.
#
# Asserts:
#   (a) scope-guard.sh source contains .rabbit-scope-override in its allowlist check
#   (b) piping a Write JSON for .rabbit-scope-override to scope-guard.sh exits 0 (ALLOW)
#       without any scope marker active
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.sh"

FAILURES=0
TOTAL=0

ok() {
    TOTAL=$(( TOTAL + 1 ))
    echo "  PASS t$TOTAL: $1"
}

fail_t() {
    TOTAL=$(( TOTAL + 1 ))
    FAILURES=$(( FAILURES + 1 ))
    echo "  FAIL t$TOTAL: $1"
}

echo "test-scope-guard-allowlist.sh"
echo ""
echo "=== (a) scope-guard.sh source contains .rabbit-scope-override in allowlist ==="

# t1: scope-guard.sh must reference .rabbit-scope-override in its allowlist if-statement
# Check for the pattern: [ "$base" = ".rabbit-scope-override" ] inside the allowlist block
if grep -qE '\[ "\$base" = "\.rabbit-scope-override" \]' "$SCOPE_GUARD" 2>/dev/null; then
    ok "scope-guard.sh allowlist if-statement includes .rabbit-scope-override"
else
    fail_t "scope-guard.sh does NOT contain .rabbit-scope-override in allowlist if-statement"
fi

echo ""
echo "=== (b) Write to .rabbit-scope-override is ALLOW without scope marker ==="

# Ensure no scope markers are present (clean environment)
MARKER="$REPO_ROOT/.rabbit-scope-active"
MARKER_EXISTED=0
MARKER_BACKUP=""
if [ -f "$MARKER" ]; then
    MARKER_EXISTED=1
    MARKER_BACKUP="$(cat "$MARKER")"
    rm -f "$MARKER"
fi

# Remove any per-feature markers that might be present
shopt -s nullglob 2>/dev/null || true
for per_marker in "$REPO_ROOT"/.rabbit-scope-active-*; do
    [ -f "$per_marker" ] && rm -f "$per_marker"
done

# t2: Write JSON for .rabbit-scope-override at repo root must exit 0 (allow) with no scope marker
write_json='{"tool_name":"Write","tool_input":{"file_path":"'"$REPO_ROOT"'/.rabbit-scope-override","content":"one-time"}}'
t2_exit=0
echo "$write_json" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t2_exit=$?

if [ "$t2_exit" -eq 0 ]; then
    ok "Write to .rabbit-scope-override exits 0 (ALLOW) without any scope marker active"
else
    fail_t "Write to .rabbit-scope-override exits $t2_exit (expected 0/ALLOW) without scope marker — catch-22 not fixed"
fi

# t3: Write JSON for .rabbit-scope-override using relative path also exits 0
write_json_rel='{"tool_name":"Write","tool_input":{"file_path":".rabbit-scope-override","content":"one-time"}}'
t3_exit=0
echo "$write_json_rel" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t3_exit=$?

if [ "$t3_exit" -eq 0 ]; then
    ok "Write to .rabbit-scope-override (relative path) exits 0 (ALLOW) without scope marker"
else
    fail_t "Write to .rabbit-scope-override (relative path) exits $t3_exit (expected 0/ALLOW)"
fi

# Restore marker if it existed
if [ "$MARKER_EXISTED" -eq 1 ]; then
    echo "$MARKER_BACKUP" > "$MARKER"
fi

echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
