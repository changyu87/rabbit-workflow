#!/usr/bin/env bash
# test-rabbit-config-permissions.sh
# Tests for /rabbit-config permission subcommands:
#   - allowed-tools add/remove/list
#   - bash-allow add/remove/list
# Operates on a temporary settings.json so the real one is not touched.

set -uo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
COMMANDS_DIR="$REPO_ROOT/.claude/features/rabbit-cage/commands"
CONFIG_MD="$COMMANDS_DIR/rabbit-config.md"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

echo "test-rabbit-config-permissions.sh"

# Helper: extract the python3 body from rabbit-config.md and run it with given ARGUMENTS
# in a working dir that contains the test settings.json under .claude/.
# The command file uses `python3 -c "..."` so we extract the body between the first
# `python3 -c "` and the closing `"` that terminates the backtick block.
extract_pyscript() {
    python3 - "$CONFIG_MD" <<'PYEOF'
import re, sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text()
# Find: python3 -c "<body>"`
# Body may span lines; ends with `"` followed by a backtick.
m = re.search(r'python3 -c "(.*?)"`', text, re.DOTALL)
if not m:
    sys.exit("could not find python3 -c block in command file")
sys.stdout.write(m.group(1))
PYEOF
}

run_config() {
    # $1 = ARGUMENTS string
    # $2 = working directory (must contain .claude/settings.json)
    local argstr="$1" wd="$2"
    local script
    script="$(extract_pyscript)"
    if [ -z "$script" ]; then
        echo "EXTRACT_FAILED" >&2
        return 1
    fi
    ( cd "$wd" && ARGUMENTS="$argstr" python3 -c "$script" )
}

setup_workspace() {
    # Create a temp workspace with .claude/settings.json initialized to an empty JSON object.
    local wd
    wd="$(mktemp -d)"
    mkdir -p "$wd/.claude"
    echo '{}' > "$wd/.claude/settings.json"
    echo "$wd"
}

read_perm_allow() {
    # $1 = working dir; print JSON array of permissions.allow (or [] if absent)
    python3 -c "
import json, pathlib
p = pathlib.Path('$1/.claude/settings.json')
d = json.loads(p.read_text()) if p.exists() else {}
print(json.dumps(d.get('permissions', {}).get('allow', [])))
"
}

# t1: allowed-tools add <tool> writes the entry
WD1="$(setup_workspace)"
out1="$(run_config "allowed-tools add WebFetch" "$WD1" 2>&1)"
rc1=$?
allow1="$(read_perm_allow "$WD1")"
if [ $rc1 -eq 0 ] && [ "$allow1" = '["WebFetch"]' ]; then
    ok 1 "allowed-tools add WebFetch creates permissions.allow with WebFetch"
else
    fail_t 1 "allowed-tools add failed (rc=$rc1, allow=$allow1, out=$out1)"
fi
rm -rf "$WD1"

# t2: allowed-tools add idempotent (no duplicate)
WD2="$(setup_workspace)"
run_config "allowed-tools add WebFetch" "$WD2" >/dev/null 2>&1
run_config "allowed-tools add WebFetch" "$WD2" >/dev/null 2>&1
allow2="$(read_perm_allow "$WD2")"
if [ "$allow2" = '["WebFetch"]' ]; then
    ok 2 "allowed-tools add is idempotent (no duplicate WebFetch)"
else
    fail_t 2 "allowed-tools add not idempotent (allow=$allow2)"
fi
rm -rf "$WD2"

# t3: allowed-tools remove <tool> removes the entry
WD3="$(setup_workspace)"
run_config "allowed-tools add Edit"  "$WD3" >/dev/null 2>&1
run_config "allowed-tools add Write" "$WD3" >/dev/null 2>&1
run_config "allowed-tools remove Edit" "$WD3" >/dev/null 2>&1
allow3="$(read_perm_allow "$WD3")"
if [ "$allow3" = '["Write"]' ]; then
    ok 3 "allowed-tools remove Edit leaves only Write"
else
    fail_t 3 "allowed-tools remove failed (allow=$allow3)"
fi
rm -rf "$WD3"

# t4: allowed-tools remove of absent entry is no-op (exit 0)
WD4="$(setup_workspace)"
run_config "allowed-tools remove DoesNotExist" "$WD4" >/dev/null 2>&1
rc4=$?
allow4="$(read_perm_allow "$WD4")"
if [ $rc4 -eq 0 ] && [ "$allow4" = '[]' ]; then
    ok 4 "allowed-tools remove of absent entry is no-op"
else
    fail_t 4 "allowed-tools remove of absent entry failed (rc=$rc4, allow=$allow4)"
fi
rm -rf "$WD4"

# t5: allowed-tools (no args) lists current entries
WD5="$(setup_workspace)"
run_config "allowed-tools add Edit"  "$WD5" >/dev/null 2>&1
run_config "allowed-tools add Write" "$WD5" >/dev/null 2>&1
list5="$(run_config "allowed-tools" "$WD5" 2>/dev/null)"
if echo "$list5" | grep -qx "Edit" && echo "$list5" | grep -qx "Write"; then
    ok 5 "allowed-tools (no action) lists entries one per line"
else
    fail_t 5 "allowed-tools list missing entries (got: $list5)"
fi
rm -rf "$WD5"

# t6: bash-allow add <cmd> writes Bash(cmd:*) into permissions.allow
WD6="$(setup_workspace)"
out6="$(run_config "bash-allow add touch" "$WD6" 2>&1)"
rc6=$?
allow6="$(read_perm_allow "$WD6")"
if [ $rc6 -eq 0 ] && [ "$allow6" = '["Bash(touch:*)"]' ]; then
    ok 6 "bash-allow add touch writes Bash(touch:*) to permissions.allow"
else
    fail_t 6 "bash-allow add failed (rc=$rc6, allow=$allow6, out=$out6)"
fi
rm -rf "$WD6"

# t7: bash-allow add idempotent
WD7="$(setup_workspace)"
run_config "bash-allow add cat" "$WD7" >/dev/null 2>&1
run_config "bash-allow add cat" "$WD7" >/dev/null 2>&1
allow7="$(read_perm_allow "$WD7")"
if [ "$allow7" = '["Bash(cat:*)"]' ]; then
    ok 7 "bash-allow add is idempotent"
else
    fail_t 7 "bash-allow add not idempotent (allow=$allow7)"
fi
rm -rf "$WD7"

# t8: bash-allow remove <cmd> removes Bash(cmd:*)
WD8="$(setup_workspace)"
run_config "bash-allow add touch" "$WD8" >/dev/null 2>&1
run_config "bash-allow add cat"   "$WD8" >/dev/null 2>&1
run_config "bash-allow remove touch" "$WD8" >/dev/null 2>&1
allow8="$(read_perm_allow "$WD8")"
if [ "$allow8" = '["Bash(cat:*)"]' ]; then
    ok 8 "bash-allow remove touch leaves only Bash(cat:*)"
else
    fail_t 8 "bash-allow remove failed (allow=$allow8)"
fi
rm -rf "$WD8"

# t9: bash-allow (no action) lists current commands (inner names only)
WD9="$(setup_workspace)"
run_config "bash-allow add touch"  "$WD9" >/dev/null 2>&1
run_config "bash-allow add echo"   "$WD9" >/dev/null 2>&1
run_config "bash-allow add ls"     "$WD9" >/dev/null 2>&1
run_config "bash-allow add python" "$WD9" >/dev/null 2>&1
list9="$(run_config "bash-allow" "$WD9" 2>/dev/null)"
miss=""
for c in touch echo ls python; do
    if ! echo "$list9" | grep -qx "$c"; then
        miss="$miss $c"
    fi
done
if [ -z "$miss" ]; then
    ok 9 "bash-allow (no action) lists touch/echo/ls/python"
else
    fail_t 9 "bash-allow list missing:$miss (got: $list9)"
fi
rm -rf "$WD9"

# t10: invalid bash-allow command (contains '(') is rejected
WD10="$(setup_workspace)"
out10="$(run_config "bash-allow add bad(name" "$WD10" 2>&1)"
rc10=$?
allow10="$(read_perm_allow "$WD10")"
if [ $rc10 -ne 0 ] && [ "$allow10" = '[]' ]; then
    ok 10 "bash-allow add rejects command containing parens"
else
    fail_t 10 "bash-allow add accepted invalid command (rc=$rc10, allow=$allow10)"
fi
rm -rf "$WD10"

# t11: allowed-tools rejects Bash(...) inputs (must use bash-allow)
WD11="$(setup_workspace)"
out11="$(run_config "allowed-tools add Bash(touch:*)" "$WD11" 2>&1)"
rc11=$?
allow11="$(read_perm_allow "$WD11")"
if [ $rc11 -ne 0 ] && [ "$allow11" = '[]' ]; then
    ok 11 "allowed-tools add rejects Bash(...) inputs"
else
    fail_t 11 "allowed-tools add accepted Bash(...) input (rc=$rc11, allow=$allow11)"
fi
rm -rf "$WD11"

# t12: unknown action under allowed-tools is rejected (no file modification)
WD12="$(setup_workspace)"
out12="$(run_config "allowed-tools whatever Foo" "$WD12" 2>&1)"
rc12=$?
allow12="$(read_perm_allow "$WD12")"
if [ $rc12 -ne 0 ] && [ "$allow12" = '[]' ]; then
    ok 12 "allowed-tools rejects unknown action"
else
    fail_t 12 "allowed-tools accepted unknown action (rc=$rc12, allow=$allow12)"
fi
rm -rf "$WD12"

# t13: writes go to settings.json (NOT settings.local.json)
WD13="$(setup_workspace)"
run_config "bash-allow add touch" "$WD13" >/dev/null 2>&1
if [ ! -f "$WD13/.claude/settings.local.json" ] && [ -f "$WD13/.claude/settings.json" ]; then
    ok 13 "permission subcommands write to settings.json, not settings.local.json"
else
    fail_t 13 "settings.local.json was created (or settings.json missing) — wrong target file"
fi
rm -rf "$WD13"

# t14: spec.md mentions allowed-tools and bash-allow subcommands
SPEC_MD="$REPO_ROOT/.claude/features/rabbit-cage/docs/spec/spec.md"
if grep -q "allowed-tools" "$SPEC_MD" && grep -q "bash-allow" "$SPEC_MD"; then
    ok 14 "spec.md declares allowed-tools and bash-allow subcommands"
else
    fail_t 14 "spec.md missing allowed-tools and/or bash-allow declaration"
fi

# t15: contract.md subcommands list mentions allowed-tools and bash-allow
CONTRACT_MD="$REPO_ROOT/.claude/features/rabbit-cage/docs/spec/contract.md"
if grep -q "allowed-tools" "$CONTRACT_MD" && grep -q "bash-allow" "$CONTRACT_MD"; then
    ok 15 "contract.md subcommands list includes allowed-tools and bash-allow"
else
    fail_t 15 "contract.md missing allowed-tools and/or bash-allow in subcommands list"
fi

# t16: empty bash-allow command rejected
WD16="$(setup_workspace)"
out16="$(run_config "bash-allow add" "$WD16" 2>&1)"
rc16=$?
allow16="$(read_perm_allow "$WD16")"
if [ $rc16 -ne 0 ] && [ "$allow16" = '[]' ]; then
    ok 16 "bash-allow add with no value rejected"
else
    fail_t 16 "bash-allow add with no value accepted (rc=$rc16, allow=$allow16)"
fi
rm -rf "$WD16"

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
