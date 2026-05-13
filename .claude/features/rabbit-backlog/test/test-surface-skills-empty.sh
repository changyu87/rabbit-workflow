#!/usr/bin/env bash
# test-surface-skills-empty.sh — asserts surface.skills is [] in feature.json.
#
# Invariant: surface.skills MUST be [] (empty array).
# Skills are managed via build-contract.json copy-file entries.
# The surface.skills field in feature.json is the retired mechanism.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
FEATURE_DIR="${REPO_ROOT}/.claude/features/rabbit-backlog"
FEATURE_JSON="${FEATURE_DIR}/feature.json"

pass=0
fail=0

ok() {
    echo "  PASS  $1"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL  $1${2:+ -- $2}"
    fail=$((fail + 1))
}

echo "=== test-surface-skills-empty.sh: surface.skills must be [] ==="
echo ""

# t1: feature.json exists
if [ -f "$FEATURE_JSON" ]; then
    ok "t1: feature.json exists"
else
    fail_t "t1: feature.json exists" "not found: $FEATURE_JSON"
fi

# t2: surface.skills is [] (empty array)
if [ -f "$FEATURE_JSON" ]; then
    result=$(python3 - "$FEATURE_JSON" <<'PYEOF' 2>/dev/null
import sys, json
d = json.load(open(sys.argv[1]))
skills = d.get("surface", {}).get("skills", None)
if skills is None:
    print("surface.skills key missing")
elif not isinstance(skills, list):
    print(f"surface.skills is not a list: {skills!r}")
elif len(skills) != 0:
    print(f"surface.skills is not empty: {skills!r}")
PYEOF
)
    if [ -z "$result" ]; then
        ok "t2: surface.skills is [] (empty array)"
    else
        fail_t "t2: surface.skills is [] (empty array)" "$result"
    fi
else
    fail_t "t2: surface.skills is [] (empty array)" \
           "feature.json not found (t1 prerequisite failed)"
fi

echo ""
echo "Results: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
