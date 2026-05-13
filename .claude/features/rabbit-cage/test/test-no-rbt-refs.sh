#!/usr/bin/env bash
# test-no-rbt-refs.sh
# Asserts that rabbit-cage implementation source files contain no ".rbt-" references.
# The .rbt- prefix migration is complete; the shim and all dead references
# must be removed. Any remaining .rbt- reference in source is a stale artifact.
#
# Scans: hooks/, scripts/, commands/, docs/, settings.json, feature.json
# Exclusions: test/ (tests legitimately assert absence of rbt- patterns),
#             bugs/ and archive/ (historical records, not source)
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
FEATURE_DIR="$REPO_ROOT/.claude/features/rabbit-cage"

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

echo "test-no-rbt-refs.sh"
echo ""

# ---------------------------------------------------------------------------
# t1: session-init.sh (feature copy) has no .rbt- references
# ---------------------------------------------------------------------------
echo "=== t1: .claude/features/rabbit-cage/hooks/session-init.sh has no .rbt- refs ==="

SESSION_INIT_FEATURE="$FEATURE_DIR/hooks/session-init.sh"
if grep -q '\.rbt-' "$SESSION_INIT_FEATURE" 2>/dev/null; then
    MATCHES="$(grep -n '\.rbt-' "$SESSION_INIT_FEATURE" | head -5)"
    fail_t "session-init.sh (feature) still contains .rbt- references:
$MATCHES"
else
    ok "session-init.sh (feature) has no .rbt- references"
fi

# ---------------------------------------------------------------------------
# t2: session-init.sh (deployed hooks copy) has no .rbt- references
# ---------------------------------------------------------------------------
echo "=== t2: .claude/hooks/session-init.sh has no .rbt- refs ==="

SESSION_INIT_DEPLOYED="$REPO_ROOT/.claude/hooks/session-init.sh"
if [ -L "$SESSION_INIT_DEPLOYED" ]; then
    SESSION_INIT_DEPLOYED_REAL="$(readlink -f "$SESSION_INIT_DEPLOYED" 2>/dev/null || echo "$SESSION_INIT_DEPLOYED")"
else
    SESSION_INIT_DEPLOYED_REAL="$SESSION_INIT_DEPLOYED"
fi

if grep -q '\.rbt-' "$SESSION_INIT_DEPLOYED_REAL" 2>/dev/null; then
    MATCHES="$(grep -n '\.rbt-' "$SESSION_INIT_DEPLOYED_REAL" | head -5)"
    fail_t "session-init.sh (deployed) still contains .rbt- references:
$MATCHES"
else
    ok "session-init.sh (deployed) has no .rbt- references"
fi

# ---------------------------------------------------------------------------
# t3: spec.md has no .rbt- references
# ---------------------------------------------------------------------------
echo "=== t3: spec.md has no .rbt- refs ==="

SPEC_MD="$FEATURE_DIR/docs/spec/spec.md"
if grep -q '\.rbt-' "$SPEC_MD" 2>/dev/null; then
    MATCHES="$(grep -n '\.rbt-' "$SPEC_MD" | head -5)"
    fail_t "spec.md still contains .rbt- references:
$MATCHES"
else
    ok "spec.md has no .rbt- references"
fi

# ---------------------------------------------------------------------------
# t4: contract.md has no .rbt- references
# ---------------------------------------------------------------------------
echo "=== t4: contract.md has no .rbt- refs ==="

CONTRACT_MD="$FEATURE_DIR/docs/spec/contract.md"
if grep -q '\.rbt-' "$CONTRACT_MD" 2>/dev/null; then
    MATCHES="$(grep -n '\.rbt-' "$CONTRACT_MD" | head -5)"
    fail_t "contract.md still contains .rbt- references:
$MATCHES"
else
    ok "contract.md has no .rbt- references"
fi

# ---------------------------------------------------------------------------
# t5: all rabbit-cage implementation source files have no .rbt- references
#     Scans hooks/, scripts/, commands/, docs/, and top-level json files.
#     Excludes test/ (tests assert absence of rbt- and may grep for it),
#     bugs/, and archive/ (historical records).
# ---------------------------------------------------------------------------
echo "=== t5: all rabbit-cage source (non-test) files have no .rbt- refs ==="

FOUND_FILES=()
SOURCE_DIRS=(
    "$FEATURE_DIR/hooks"
    "$FEATURE_DIR/scripts"
    "$FEATURE_DIR/commands"
    "$FEATURE_DIR/docs"
)

for dir in "${SOURCE_DIRS[@]}"; do
    [ -d "$dir" ] || continue
    while IFS= read -r -d '' file; do
        if grep -q '\.rbt-' "$file" 2>/dev/null; then
            FOUND_FILES+=("$file")
        fi
    done < <(find "$dir" -type f -print0)
done

# Also check top-level json files in the feature dir
for json_file in "$FEATURE_DIR/feature.json" "$FEATURE_DIR/settings.json"; do
    [ -f "$json_file" ] || continue
    if grep -q '\.rbt-' "$json_file" 2>/dev/null; then
        FOUND_FILES+=("$json_file")
    fi
done

if [ "${#FOUND_FILES[@]}" -eq 0 ]; then
    ok "no rabbit-cage source files contain .rbt- references"
else
    fail_t "the following rabbit-cage source files still contain .rbt- references:"
    for f in "${FOUND_FILES[@]}"; do
        echo "    $f:"
        grep -n '\.rbt-' "$f" | head -3 | sed 's/^/      /'
    done
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
