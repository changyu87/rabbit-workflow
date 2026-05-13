#!/usr/bin/env bash
# test-RABBIT-CAGE-BACKLOG14-conditional-priority.sh
# Tests that sync-check.sh implements the conditional-priority multi-message strategy
# declared in spec Invariants 37 and 38 (RABBIT-CAGE-BACKLOG-14).
#
# Strategy: conditional-priority — when multiple conditions are simultaneously true,
# only the highest-priority condition emits. Priority order (highest to lowest):
#   1. CLAUDE.md drift or first-run
#   2. Surface drift
#   3. Scope-guard-off (session override active or one-time override consumed)
#   4. Plugins-stale
#
# R3-compliant: no interactive constructs, fully automated.
# E2E: exercises sync-check.sh from entry point through final output.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.sh"

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

extract_sys_msg() {
    python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('systemMessage', ''), end='')
except Exception:
    pass
" 2>/dev/null
}

# Returns count of valid JSON objects in stdin
count_json_objects() {
    python3 -c "
import sys, json
data = sys.stdin.read().strip()
if not data:
    print(0)
    sys.exit(0)
try:
    json.loads(data)
    print(1)
    sys.exit(0)
except Exception:
    pass
decoder = json.JSONDecoder()
idx = 0
count = 0
while idx < len(data):
    data_slice = data[idx:].lstrip()
    if not data_slice:
        break
    try:
        obj, end = decoder.raw_decode(data_slice)
        count += 1
        idx += len(data) - len(data_slice) + end
    except:
        break
print(count)
" 2>/dev/null
}

# Build a minimal temp git repo with CLAUDE.md matching generated output.
# The returned directory is a clean repo where sync-check.sh emits nothing.
make_clean_repo() {
    local d
    d="$(mktemp -d)"
    git init -q "$d"
    git -C "$d" config user.email "test@test.com"
    git -C "$d" config user.name "Test"
    git -C "$d" checkout -q -b main 2>/dev/null || true

    mkdir -p "$d/.claude/features/rabbit-cage/scripts"
    mkdir -p "$d/.claude/features/policy"

    printf '# Philosophy\nMachine First.\n'   > "$d/.claude/features/policy/philosophy.md"
    printf '# Spec Rules\nSpec.\n'            > "$d/.claude/features/policy/spec-rules.md"
    printf '# Coding Rules\nCode.\n'          > "$d/.claude/features/policy/coding-rules.md"
    printf '# Workflow Rules\nWorkflow.\n'    > "$d/.claude/features/policy/workflow-rules.md"

    python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
        > "$d/.claude/features/rabbit-cage/policy-header.json"

    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
       "$d/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

    python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
        > "$d/.claude/features/registry.json"

    local correct
    correct="$(RABBIT_ROOT="$d" bash "$d/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
    printf '%s\n' "$correct" > "$d/CLAUDE.md"

    git -C "$d" add -A
    git -C "$d" commit -q -m "init"

    echo "$d"
}

echo "test-RABBIT-CAGE-BACKLOG14-conditional-priority.sh"
echo "Asserting spec Invariants 37 and 38: conditional-priority strategy"
echo ""

TMPROOT=""
cleanup() { rm -rf "$TMPROOT" 2>/dev/null || true; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# t1: Schema conformance — output is valid JSON with systemMessage when emitting
# (Invariant 38: systemMessage always present when JSON emitted)
# ---------------------------------------------------------------------------
echo "=== t1: schema conformance — systemMessage always present when emitting ==="

TMPROOT="$(make_clean_repo)"
touch "$TMPROOT/.rabbit-plugins-stale"

t1_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t1_has_sys_msg="$(printf '%s' "$t1_output" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('yes' if 'systemMessage' in d else 'no')
except Exception:
    print('no')
" 2>/dev/null)"

if [ "$t1_has_sys_msg" = "yes" ]; then
    ok "systemMessage field present in emitted JSON (Invariant 38)"
else
    fail_t "systemMessage field MISSING from emitted JSON — violates Invariant 38 (output: $(printf '%q' "$t1_output"))"
fi

# ---------------------------------------------------------------------------
# t2: Schema conformance — no additionalContext on plugins-stale path
# (Invariant 38: additionalContext only on CLAUDE.md paths)
# ---------------------------------------------------------------------------
echo "=== t2: no additionalContext on plugins-stale path (Invariant 38) ==="

t2_has_ctx="$(printf '%s' "$t1_output" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('yes' if 'additionalContext' in d else 'no')
except Exception:
    print('no')
" 2>/dev/null)"

if [ "$t2_has_ctx" = "no" ]; then
    ok "additionalContext absent on plugins-stale path (Invariant 38)"
else
    fail_t "additionalContext present on plugins-stale path — must only appear on CLAUDE.md paths (Invariant 38)"
fi
rm -rf "$TMPROOT" 2>/dev/null || true

# ---------------------------------------------------------------------------
# t3: Priority — scope-guard-off suppresses plugins-stale
# When both .rabbit-scope-override=session AND .rabbit-plugins-stale exist:
# scope-guard-off (priority 3) must emit; plugins-stale (priority 4) must be suppressed.
# (Invariant 37: scope-guard-off beats plugins-stale)
# ---------------------------------------------------------------------------
echo "=== t3: scope-guard-off suppresses plugins-stale (Invariant 37, priority 3>4) ==="

TMPROOT="$(make_clean_repo)"
printf 'session' > "$TMPROOT/.rabbit-scope-override"
touch "$TMPROOT/.rabbit-plugins-stale"

t3_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t3_msg="$(printf '%s' "$t3_output" | extract_sys_msg)"
t3_json_count="$(printf '%s' "$t3_output" | count_json_objects)"

# Must emit exactly one JSON object
if [ "$t3_json_count" = "1" ]; then
    ok "exactly one JSON object emitted when scope-guard-off AND plugins-stale (Invariant 37)"
else
    fail_t "expected 1 JSON object, got $t3_json_count — violates single-JSON invariant"
fi

# That JSON must be the scope-guard-off alert (not the plugins alert)
if printf '%s' "$t3_msg" | grep -qi 'SCOPE GUARD\|scope guard\|override' 2>/dev/null; then
    ok "scope-guard-off alert emitted (higher priority wins, Invariant 37)"
else
    fail_t "scope-guard-off alert NOT emitted — expected SCOPE GUARD message, got: $(printf '%q' "$t3_msg")"
fi

# plugins-stale message must NOT appear
if printf '%s' "$t3_msg" | grep -qi 'rabbit-refresh\|reload-plugins\|Plugins updated' 2>/dev/null; then
    fail_t "plugins-stale alert leaked through — lower priority should be suppressed (Invariant 37)"
else
    ok "plugins-stale suppressed when scope-guard-off active (Invariant 37)"
fi
rm -rf "$TMPROOT" 2>/dev/null || true

# ---------------------------------------------------------------------------
# t4: Priority — scope-guard-bypass suppresses plugins-stale
# When .rabbit-scope-override-used AND .rabbit-plugins-stale exist:
# scope-guard-bypass (priority 3, sub-case of scope-guard-off) beats plugins-stale.
# (Invariant 37)
# ---------------------------------------------------------------------------
echo "=== t4: scope-guard-bypass suppresses plugins-stale (Invariant 37) ==="

TMPROOT="$(make_clean_repo)"
touch "$TMPROOT/.rabbit-scope-override-used"
touch "$TMPROOT/.rabbit-plugins-stale"

t4_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t4_msg="$(printf '%s' "$t4_output" | extract_sys_msg)"
t4_json_count="$(printf '%s' "$t4_output" | count_json_objects)"

if [ "$t4_json_count" = "1" ]; then
    ok "exactly one JSON object when scope-guard-bypass AND plugins-stale"
else
    fail_t "expected 1 JSON object, got $t4_json_count"
fi

if printf '%s' "$t4_msg" | grep -qi 'BYPASSED\|bypass\|SCOPE GUARD\|scope guard' 2>/dev/null; then
    ok "scope-guard-bypass alert emitted (higher priority wins, Invariant 37)"
else
    fail_t "scope-guard-bypass alert NOT emitted — expected BYPASSED message, got: $(printf '%q' "$t4_msg")"
fi

if printf '%s' "$t4_msg" | grep -qi 'rabbit-refresh\|reload-plugins\|Plugins updated' 2>/dev/null; then
    fail_t "plugins-stale leaked through when scope-guard-bypass active (Invariant 37)"
else
    ok "plugins-stale suppressed when scope-guard-bypass active (Invariant 37)"
fi
rm -rf "$TMPROOT" 2>/dev/null || true

# ---------------------------------------------------------------------------
# t5: Spec declares strategy as conditional-priority
# (Invariant 24f: strategy keyword must appear in spec)
# ---------------------------------------------------------------------------
echo "=== t5: spec.md declares conditional-priority strategy (Invariant 24f) ==="

SPEC_FILE="$REPO_ROOT/.claude/features/rabbit-cage/docs/spec/spec.md"

if grep -q 'conditional-priority' "$SPEC_FILE" 2>/dev/null; then
    ok "spec.md contains 'conditional-priority' keyword (Invariant 24f)"
else
    fail_t "spec.md does NOT contain 'conditional-priority' — strategy not declared in spec"
fi

# ---------------------------------------------------------------------------
# t6: Spec declares explicit priority order with all 4 conditions
# (Invariant 37: priority order explicitly listed)
# ---------------------------------------------------------------------------
echo "=== t6: spec.md declares all 4 priority conditions (Invariant 37) ==="

priority_conditions_found=0
grep -qiE 'CLAUDE\.md drift' "$SPEC_FILE" 2>/dev/null && priority_conditions_found=$(( priority_conditions_found + 1 ))
grep -qiE 'Surface drift|surface-drift' "$SPEC_FILE" 2>/dev/null && priority_conditions_found=$(( priority_conditions_found + 1 ))
grep -qiE 'Scope-guard-off|scope guard off' "$SPEC_FILE" 2>/dev/null && priority_conditions_found=$(( priority_conditions_found + 1 ))
grep -qiE 'Plugins-stale|plugins stale' "$SPEC_FILE" 2>/dev/null && priority_conditions_found=$(( priority_conditions_found + 1 ))

if [ "$priority_conditions_found" -ge 4 ]; then
    ok "all 4 priority conditions referenced in spec (Invariant 37)"
else
    fail_t "only $priority_conditions_found of 4 priority conditions found in spec — Invariant 37 requires all 4 explicitly declared"
fi

# ---------------------------------------------------------------------------
# t7: Contract declares sync-check-output schema
# (Invariant 38: schema must be machine-first, declared in contract)
# ---------------------------------------------------------------------------
echo "=== t7: contract.md declares sync-check-output schema (Invariant 38) ==="

CONTRACT_FILE="$REPO_ROOT/.claude/features/rabbit-cage/docs/spec/contract.md"

if grep -q 'sync-check-output' "$CONTRACT_FILE" 2>/dev/null; then
    ok "contract.md contains 'sync-check-output' schema (Invariant 38)"
else
    fail_t "contract.md does NOT declare 'sync-check-output' schema — violates machine-first requirement (Invariant 38)"
fi

if grep -q 'conditional-priority' "$CONTRACT_FILE" 2>/dev/null; then
    ok "contract.md declares 'conditional-priority' strategy in schema (Invariant 38)"
else
    fail_t "contract.md does NOT declare 'conditional-priority' strategy in schema"
fi

if grep -q 'priority_order' "$CONTRACT_FILE" 2>/dev/null; then
    ok "contract.md includes priority_order field in schema"
else
    fail_t "contract.md schema missing 'priority_order' field — schema is incomplete"
fi

# ---------------------------------------------------------------------------
# t8: Invariant 37 explicitly numbered in spec
# ---------------------------------------------------------------------------
echo "=== t8: spec.md contains Invariant 37 with priority order ==="

if grep -q '^37\.' "$SPEC_FILE" 2>/dev/null; then
    ok "Invariant 37 present in spec.md"
else
    fail_t "Invariant 37 NOT found in spec.md — must be explicitly numbered per spec style"
fi

if grep -q '^38\.' "$SPEC_FILE" 2>/dev/null; then
    ok "Invariant 38 present in spec.md"
else
    fail_t "Invariant 38 NOT found in spec.md — output schema must be codified as invariant"
fi

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
