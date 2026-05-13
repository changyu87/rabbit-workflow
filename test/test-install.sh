#!/usr/bin/env bash
# E2E tests for install.sh. Run: bash test/test-install.sh

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"
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
    [[ -x "$DIR/.claude/hooks/refresh.sh" ]]
}

t3_settings_content() {
    "$INSTALL" "$DIR" >/dev/null
    python3 -c "
import json
data = json.load(open('$DIR/.claude/settings.json'))
assert data['env']['RABBIT_REFRESH_EVERY'] == '20', repr(data)
"
}

t4_claude_imports() {
    "$INSTALL" "$DIR" >/dev/null
    grep -q 'rabbit-policy-start' "$DIR/CLAUDE.md" &&
    grep -q 'rabbit-policy-end' "$DIR/CLAUDE.md"
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
    echo 19 >"$DIR/.rabbit-prompt-counter"
    local out ret
    out="$(mktemp)"
    (cd "$DIR" && RABBIT_ROOT="$DIR" RABBIT_REFRESH_EVERY=20 .claude/hooks/refresh.sh >"$out")
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
        "$DIR/.claude/commands/rabbit-config.md")
    ! (cd "$DIR" && ARGUMENTS="prompt-threshold abc" python3 -c "$pyblock")
}

t8b_threshold_valid_writes_json() {
    "$INSTALL" "$DIR" >/dev/null
    local pyblock
    pyblock=$(sed -n '/python3 -c "/,/^"`$/{/python3 -c "/d; /^"`$/d; p}' \
        "$DIR/.claude/commands/rabbit-config.md")
    (cd "$DIR" && ARGUMENTS="prompt-threshold 15" python3 -c "$pyblock" >/dev/null)
    python3 -c "
import json
data = json.load(open('$DIR/.claude/settings.local.json'))
assert data['env']['RABBIT_REFRESH_EVERY'] == '15', repr(data)
"
}

t9_no_settings_local_installed() {
    "$INSTALL" "$DIR" >/dev/null
    [[ ! -f "$DIR/.claude/settings.local.json" ]]
}

# --all flag tests

t10_default_strips_specs_and_plans() {
    "$INSTALL" "$DIR" >/dev/null
    # Default install strips .claude/docs/specs/*.md and docs/plans/*.md.
    # The dirs may or may not exist; we just assert no .md files remain.
    ! ls "$DIR/.claude/docs/specs/"*.md 2>/dev/null
    ! ls "$DIR/.claude/docs/plans/"*.md 2>/dev/null
}

t11_default_no_archive_no_test_dir() {
    "$INSTALL" "$DIR" >/dev/null
    [[ ! -d "$DIR/archive" ]] && [[ ! -d "$DIR/test" ]]
}

t12_all_keeps_specs_and_plans_if_present() {
    "$INSTALL" --all "$DIR" >/dev/null
    # If source had specs/plans, they should still exist post-install
    if ls "$REPO_ROOT/.claude/docs/specs/"*.md 2>/dev/null >/dev/null; then
        ls "$DIR/.claude/docs/specs/"*.md 2>/dev/null >/dev/null
    else
        true   # nothing to assert if source has nothing
    fi
}

t13_all_includes_archive_and_test_when_present() {
    "$INSTALL" --all "$DIR" >/dev/null
    # If source had archive/, target should too
    if [[ -d "$REPO_ROOT/archive" ]]; then
        [[ -d "$DIR/archive" ]] || return 1
    fi
    if [[ -d "$REPO_ROOT/test" ]]; then
        [[ -d "$DIR/test" ]] || return 1
    fi
    return 0
}

t14_unknown_flag_rejected() {
    ! "$INSTALL" --bogus "$DIR" >/dev/null 2>&1
}

t15_all_works_with_target_first_then_flag() {
    "$INSTALL" "$DIR" --all >/dev/null
    [[ -d "$DIR/.claude" ]]
}

# ── run all ───────────────────────────────────────────────────────────────────

run "1: clean install — files present"          t1_clean_install
run "2: hook is executable"                     t2_hook_executable
run "3: settings.json has RABBIT_REFRESH_EVERY=20" t3_settings_content
run "4: CLAUDE.md imports from policy/ feature"  t4_claude_imports
run "5: existing .claude/ blocks install"       t5_existing_claude_blocked
run "6: no arg installs to \$PWD"               t6_no_arg_installs_to_pwd
run "7: hook emits valid JSON at threshold"     t7_hook_json_output
run "8a: threshold rejects invalid arg"         t8a_threshold_invalid_rejected
run "8b: threshold writes correct JSON"         t8b_threshold_valid_writes_json
run "9: settings.local.json not installed"      t9_no_settings_local_installed
run "10: default install strips docs/specs/*.md and docs/plans/*.md" t10_default_strips_specs_and_plans
run "11: default install does NOT bring archive/ or test/" t11_default_no_archive_no_test_dir
run "12: --all keeps docs/specs/ and docs/plans/" t12_all_keeps_specs_and_plans_if_present
run "13: --all includes archive/ and test/ when source has them" t13_all_includes_archive_and_test_when_present
run "14: unknown flag rejected"                 t14_unknown_flag_rejected
run "15: --all works after target arg"          t15_all_works_with_target_first_then_flag

echo ""
printf "%d passed, %d failed\n" "$PASS" "$FAIL"
[[ $FAIL -eq 0 ]]
