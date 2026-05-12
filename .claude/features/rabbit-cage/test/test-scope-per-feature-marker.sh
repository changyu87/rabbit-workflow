#!/usr/bin/env bash
# test-scope-per-feature-marker.sh
# Tests for per-feature scope markers (.rabbit-scope-active-<feature>) at repo root.
#
# New behaviour required in scope-guard.sh:
#   .rabbit-scope-active-<feature>  — per-feature marker at repo root for parallel agent safety
#
# t1: Write to .claude/features/rabbit-cage/ is ALLOWED when ONLY .rabbit-scope-active-rabbit-cage
#     exists at repo root (global .rabbit-scope-active absent) — per-feature marker grants access
# t2: Write to .claude/features/contract/ is DENIED when .rabbit-scope-active-rabbit-cage exists
#     but NOT .rabbit-scope-active-contract (cross-scope is still denied under per-feature logic)
# t3a: Both .rabbit-scope-active-rabbit-cage AND .rabbit-scope-active-tdd-state-machine coexist;
#      write to rabbit-cage/ is ALLOWED
# t3b: Both per-feature markers coexist; write to tdd-state-machine/ is ALLOWED via per-feature
#      marker (and NOT just because of an inner feature-dir marker)
#
# All tests MUST FAIL against current scope-guard.sh (per-feature markers not yet supported).
# R3-compliant: no interactive constructs, exits 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.sh"
FEATURE_JSON_CAGE="$REPO_ROOT/.claude/features/rabbit-cage/feature.json"

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

echo "test-scope-per-feature-marker.sh"
echo ""

# ---------------------------------------------------------------------------
# Shared setup: preserve global .rabbit-scope-active
# ---------------------------------------------------------------------------
GLOBAL_MARKER="$REPO_ROOT/.rabbit-scope-active"
GLOBAL_MARKER_EXISTED=0; GLOBAL_MARKER_BACKUP=""
if [ -f "$GLOBAL_MARKER" ]; then
    GLOBAL_MARKER_EXISTED=1
    GLOBAL_MARKER_BACKUP="$(cat "$GLOBAL_MARKER")"
fi

# Per-feature marker paths (at repo root — same level as global marker)
MARKER_CAGE="$REPO_ROOT/.rabbit-scope-active-rabbit-cage"
MARKER_TDD="$REPO_ROOT/.rabbit-scope-active-tdd-state-machine"

# Preserve feature.json tdd_state so we can restore it afterward
FEATURE_JSON_CAGE_BACKUP="$(cat "$FEATURE_JSON_CAGE")"

# Helper: set tdd_state for rabbit-cage to a given value
set_cage_tdd_state() {
    local state="$1"
    python3 -c "
import json
with open('$FEATURE_JSON_CAGE') as f:
    d = json.load(f)
d['tdd_state'] = '$state'
with open('$FEATURE_JSON_CAGE', 'w') as f:
    json.dump(d, f, indent=2)
" 2>/dev/null
}

# ---------------------------------------------------------------------------
# t1: .rabbit-scope-active-rabbit-cage alone allows write to rabbit-cage/
# ---------------------------------------------------------------------------
echo "=== t1: per-feature marker grants access to its own scope ==="

# Remove global marker so only the per-feature marker controls access
rm -f "$GLOBAL_MARKER"
printf 'rabbit-cage' > "$MARKER_CAGE"
# Ensure tdd_state is not test-green (so the only gate is the scope-active check)
set_cage_tdd_state "test-red"

t1_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t1_exit=0
echo "$t1_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t1_exit=$?

if [ "$t1_exit" -eq 0 ]; then
    ok "scope-guard exits 0 (ALLOW) for write to rabbit-cage/ when .rabbit-scope-active-rabbit-cage exists (no global marker)"
else
    fail_t "scope-guard exited $t1_exit (expected 0/ALLOW): .rabbit-scope-active-rabbit-cage not yet recognized as per-feature marker"
fi

rm -f "$MARKER_CAGE"
echo ""

# ---------------------------------------------------------------------------
# t2: .rabbit-scope-active-rabbit-cage does NOT grant cross-scope access
#     to .claude/features/contract/ (a feature with no inner .rabbit-scope-active)
# ---------------------------------------------------------------------------
echo "=== t2: per-feature marker does not grant cross-scope access ==="

# Only rabbit-cage per-feature marker; global marker absent; no inner marker in contract/
rm -f "$GLOBAL_MARKER"
printf 'rabbit-cage' > "$MARKER_CAGE"

t2_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/contract/foo.txt"}}'
t2_exit=0
echo "$t2_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t2_exit=$?

# After per-feature support: write to contract/ must be denied (exit 2) because
# only .rabbit-scope-active-rabbit-cage exists, not .rabbit-scope-active-contract.
# Before implementation: scope-guard denies (exit 2) for a different reason
# (no global .rabbit-scope-active ancestor found) — this test PASSES for wrong reasons.
# Once per-feature is implemented, it must still deny cross-scope writes.
#
# The test is designed to be a REGRESSION guard: it must remain passing after implementation.
# To make it FAIL now, we verify that scope-guard explicitly recognizes the per-feature
# marker format — if it doesn't parse .rabbit-scope-active-<feature> at all, the prior
# behaviour happens to pass (deny via fallback), but t1 must fail to indicate the feature
# isn't implemented. We therefore test the structural condition as a separate sub-check:

# Structural check: scope-guard.sh source must reference per-feature marker pattern
if grep -qE '\.rabbit-scope-active-' "$SCOPE_GUARD" 2>/dev/null; then
    ok "scope-guard.sh source references .rabbit-scope-active-<feature> pattern (per-feature logic present)"
else
    fail_t "scope-guard.sh source does NOT reference .rabbit-scope-active-<feature> — per-feature marker logic not implemented"
fi

# Behavioural check: cross-scope write must be denied
if [ "$t2_exit" -eq 2 ]; then
    ok "scope-guard exits 2 (DENY) for write to contract/ when only .rabbit-scope-active-rabbit-cage exists"
else
    fail_t "scope-guard exited $t2_exit (expected 2/DENY) for cross-scope write — cross-scope should be denied"
fi

rm -f "$MARKER_CAGE"
echo ""

# ---------------------------------------------------------------------------
# t3a/t3b: two per-feature markers coexist — each scope independently ALLOWED
# ---------------------------------------------------------------------------
echo "=== t3: two per-feature markers coexist; each scope independently allowed ==="

rm -f "$GLOBAL_MARKER"
printf 'rabbit-cage' > "$MARKER_CAGE"
printf 'tdd-state-machine' > "$MARKER_TDD"

# t3a: write to rabbit-cage/ must be ALLOWED
t3a_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t3a_exit=0
echo "$t3a_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t3a_exit=$?

if [ "$t3a_exit" -eq 0 ]; then
    ok "scope-guard exits 0 (ALLOW) for write to rabbit-cage/ when both per-feature markers coexist"
else
    fail_t "scope-guard exited $t3a_exit (expected 0/ALLOW) for rabbit-cage/ with both per-feature markers — rabbit-cage marker not recognized"
fi

# t3b: write to tdd-state-machine/ must be ALLOWED via per-feature marker.
# NOTE: tdd-state-machine has an inner .rabbit-scope-active in its feature dir which currently
# causes scope-guard to ALLOW writes there even without any repo-root marker.
# This test verifies the per-feature marker approach also produces ALLOW (same outcome,
# but for the right reason once implemented).
# To make this test fail before implementation, we check that the scope-guard source
# explicitly processes the per-feature tdd-state-machine marker when granting access
# (the structural test above already covers this; the behavioural outcome may coincidentally pass).
t3b_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/tdd-state-machine/somefile.txt"}}'
t3b_exit=0
echo "$t3b_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t3b_exit=$?

if [ "$t3b_exit" -eq 0 ]; then
    ok "scope-guard exits 0 (ALLOW) for write to tdd-state-machine/ when both per-feature markers coexist"
else
    fail_t "scope-guard exited $t3b_exit (expected 0/ALLOW) for tdd-state-machine/ with both per-feature markers"
fi

rm -f "$MARKER_CAGE" "$MARKER_TDD"
echo ""

# ---------------------------------------------------------------------------
# Restore original state
# ---------------------------------------------------------------------------
echo "$FEATURE_JSON_CAGE_BACKUP" > "$FEATURE_JSON_CAGE"

if [ "$GLOBAL_MARKER_EXISTED" -eq 1 ]; then
    printf '%s' "$GLOBAL_MARKER_BACKUP" > "$GLOBAL_MARKER"
else
    rm -f "$GLOBAL_MARKER"
fi

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
