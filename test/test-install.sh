#!/usr/bin/env bash
# E2E tests for install.sh. Run: bash test/test-install.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"

PASS=0
FAIL=0

run() {
    local name="$1"
    shift
    local dir
    dir="$(mktemp -d)"
    if (export DIR="$dir"; "$@") 2>/dev/null; then
        printf "PASS: %s\n" "$name"
        PASS=$((PASS + 1))
    else
        printf "FAIL: %s\n" "$name"
        FAIL=$((FAIL + 1))
    fi
    rm -rf "$dir"
}

# ── test functions ────────────────────────────────────────────────────────────

t1_clean_install() {
    "$INSTALL" "$DIR" >/dev/null
    [[ -d "$DIR/.claude" && -f "$DIR/CLAUDE.md" ]]
}

t2_hook_executable() {
    "$INSTALL" "$DIR" >/dev/null
    [[ -x "$DIR/.claude/hooks/rbt-refresh.sh" ]]
}

t3_settings_content() {
    "$INSTALL" "$DIR" >/dev/null
    python3 -c "
import json
data = json.load(open('$DIR/.claude/settings.json'))
assert data['env']['RBT_REFRESH_EVERY'] == '20', repr(data)
"
}

t4_claude_imports() {
    "$INSTALL" "$DIR" >/dev/null
    grep -q '@./.claude/philosophy.md' "$DIR/CLAUDE.md" &&
    grep -q '@./.claude/work-guide.md' "$DIR/CLAUDE.md"
}

t5_existing_claude_blocked() {
    mkdir "$DIR/.claude"
    [[ -x "$INSTALL" ]] && ! "$INSTALL" "$DIR" >/dev/null
}

t6_no_arg_installs_to_pwd() {
    (cd "$DIR" && "$INSTALL" >/dev/null)
    [[ -d "$DIR/.claude" && -f "$DIR/CLAUDE.md" ]]
}

t7_hook_json_output() {
    "$INSTALL" "$DIR" >/dev/null
    # Seed counter at THRESHOLD-1 so next increment hits threshold
    echo 19 >"$DIR/.rbt-prompt-counter"
    local out ret
    out="$(mktemp)"
    (cd "$DIR" && RBT_REFRESH_EVERY=20 .claude/hooks/rbt-refresh.sh >"$out")
    python3 - "$out" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
assert 'additionalContext' in data, f"missing additionalContext; got: {data}"
EOF
    ret=$?
    rm -f "$out"
    return $ret
}

t8a_threshold_invalid_rejected() {
    "$INSTALL" "$DIR" >/dev/null
    local pyblock
    pyblock=$(sed -n '/python3 -c "/,/^"`$/{/python3 -c "/d; /^"`$/d; p}' \
        "$DIR/.claude/commands/rabbit-set-threshold.md")
    ! (cd "$DIR" && THRESHOLD="abc" python3 -c "$pyblock")
}

t8b_threshold_valid_writes_json() {
    "$INSTALL" "$DIR" >/dev/null
    local pyblock
    pyblock=$(sed -n '/python3 -c "/,/^"`$/{/python3 -c "/d; /^"`$/d; p}' \
        "$DIR/.claude/commands/rabbit-set-threshold.md")
    (cd "$DIR" && THRESHOLD="15" python3 -c "$pyblock" >/dev/null)
    python3 -c "
import json
data = json.load(open('$DIR/.claude/settings.local.json'))
assert data['env']['RBT_REFRESH_EVERY'] == '15', repr(data)
"
}

t9_no_settings_local_installed() {
    "$INSTALL" "$DIR" >/dev/null
    [[ ! -f "$DIR/.claude/settings.local.json" ]]
}

# ── run all ───────────────────────────────────────────────────────────────────

run "1: clean install — files present"          t1_clean_install
run "2: hook is executable"                     t2_hook_executable
run "3: settings.json has RBT_REFRESH_EVERY=20" t3_settings_content
run "4: CLAUDE.md imports .claude files"        t4_claude_imports
run "5: existing .claude/ blocks install"       t5_existing_claude_blocked
run "6: no arg installs to \$PWD"               t6_no_arg_installs_to_pwd
run "7: hook emits valid JSON at threshold"     t7_hook_json_output
run "8a: threshold rejects invalid arg"         t8a_threshold_invalid_rejected
run "8b: threshold writes correct JSON"         t8b_threshold_valid_writes_json
run "9: settings.local.json not installed"      t9_no_settings_local_installed

echo ""
printf "%d passed, %d failed\n" "$PASS" "$FAIL"
[[ $FAIL -eq 0 ]]
