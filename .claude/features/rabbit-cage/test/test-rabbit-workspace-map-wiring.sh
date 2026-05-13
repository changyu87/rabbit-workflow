#!/usr/bin/env bash
# test-rabbit-workspace-map-wiring.sh
# Tests for the rabbit-workspace command removal and rabbit-workspace-map skill wiring.
#
# Spec change: rabbit-cage v1.9.0 / contract v3.5.0
#   - commands/rabbit-workspace.md removed (workspace hierarchy owned by rabbit-workspace-map)
#   - feature.json skills list wires rabbit-workspace-map
#   - feature.json commands list no longer contains rabbit-workspace
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
CAGE_DIR="$REPO_ROOT/.claude/features/rabbit-cage"
FEATURE_JSON="$CAGE_DIR/feature.json"

FAILURES=0

ok() {
    echo "  PASS t$1: $2"
}

fail_t() {
    echo "  FAIL t$1: $2"
    FAILURES=$(( FAILURES + 1 ))
}

echo "test-rabbit-workspace-map-wiring.sh"
echo ""

# t1: commands/rabbit-workspace.md must NOT exist in rabbit-cage
# The rabbit-workspace command is removed; workspace hierarchy is now owned by rabbit-workspace-map skill.
if [ ! -e "$CAGE_DIR/commands/rabbit-workspace.md" ]; then
    ok 1 "commands/rabbit-workspace.md does not exist (correctly removed)"
else
    fail_t 1 "commands/rabbit-workspace.md still exists — must be removed (workspace hierarchy owned by rabbit-workspace-map)"
fi

# t2: contract/feature.json surface.skills must be [] (skills retired from surface.skills)
# The surface.skills mechanism was retired — skills are now declared as explicit copy-file
# entries in build-contract.json. contract/feature.json surface.skills is intentionally [].
CONTRACT_FEATURE_JSON="$REPO_ROOT/.claude/features/contract/feature.json"
SKILLS_LIST="$(python3 -c "import json; d=json.load(open('$CONTRACT_FEATURE_JSON')); print(json.dumps(d.get('surface',{}).get('skills',[])))" 2>/dev/null)"
if echo "$SKILLS_LIST" | python3 -c "import json,sys; s=json.load(sys.stdin); sys.exit(0 if s == [] else 1)" 2>/dev/null; then
    ok 2 "contract/feature.json surface.skills is [] (skills retired from surface.skills mechanism)"
else
    fail_t 2 "contract/feature.json surface.skills is not [] (expected retirement; current: $SKILLS_LIST)"
fi

# t3: feature.json commands list must NOT contain rabbit-workspace
CMDS_LIST="$(python3 -c "import json; d=json.load(open('$FEATURE_JSON')); print(json.dumps(d.get('surface',{}).get('commands',[])))" 2>/dev/null)"
if echo "$CMDS_LIST" | python3 -c "import json,sys; s=json.load(sys.stdin); sys.exit(1 if any('rabbit-workspace' in c for c in s) else 0)" 2>/dev/null; then
    ok 3 "feature.json commands list does not contain rabbit-workspace"
else
    fail_t 3 "feature.json commands list still contains a rabbit-workspace entry (current: $CMDS_LIST)"
fi

# t4: The contract.md scripts list must NOT reference workspace-tree.sh
CONTRACT_MD="$CAGE_DIR/docs/spec/contract.md"
if grep -q "workspace-tree.sh" "$CONTRACT_MD" 2>/dev/null; then
    fail_t 4 "contract.md still references workspace-tree.sh — must be removed from scripts list"
else
    ok 4 "contract.md does not reference workspace-tree.sh (correctly removed from contract)"
fi

# t5: The rabbit-cage contract.md skills list must NOT reference rabbit-workspace-map
# Ownership moved to the contract feature; rabbit-cage no longer declares this skill.
if grep -q "rabbit-workspace-map" "$CONTRACT_MD" 2>/dev/null; then
    fail_t 5 "rabbit-cage contract.md still references rabbit-workspace-map — ownership moved to contract feature; remove from rabbit-cage contract.md"
else
    ok 5 "rabbit-cage contract.md does not reference rabbit-workspace-map (correctly removed; owned by contract)"
fi

echo ""
echo "Results: $(( 5 - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
