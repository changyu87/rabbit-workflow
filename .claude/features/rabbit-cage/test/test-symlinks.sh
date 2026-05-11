#!/usr/bin/env bash
# rabbit-cage symlink tests
# Tests that all required symlinks exist and point to the right targets.
# All tests must FAIL before implementation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CLAUDE_DIR="$REPO_ROOT/.claude"

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

echo "test-symlinks.sh"

# t1: .claude/agents does NOT exist (agents removed from rabbit-cage surface)
if [ ! -e "$CLAUDE_DIR/agents" ] && [ ! -L "$CLAUDE_DIR/agents" ]; then ok 1 ".claude/agents is not a symlink or does not resolve"; else fail_t 1 ".claude/agents still exists — must be removed"; fi

# t2: .claude/agents has no symlink target pointing to rabbit-cage/agents (removed)
_target="$(readlink "$CLAUDE_DIR/agents" 2>/dev/null || true)"
if [ -z "$_target" ]; then ok 2 ".claude/agents target '' does not contain 'rabbit-cage/agents'"; else fail_t 2 ".claude/agents target '$_target' still contains 'rabbit-cage/agents' — must be removed"; fi

# t3: .claude/commands is a symlink and resolves to an existing path
if [ -L "$CLAUDE_DIR/commands" ] && [ -e "$(readlink -f "$CLAUDE_DIR/commands" 2>/dev/null)" ]; then ok 3 ".claude/commands is a symlink and resolves"; else fail_t 3 ".claude/commands is not a symlink or does not resolve"; fi

# t4: .claude/commands symlink target contains "rabbit-cage/commands"
_target="$(readlink "$CLAUDE_DIR/commands" 2>/dev/null || true)"
if echo "$_target" | grep -q "rabbit-cage/commands"; then ok 4 ".claude/commands target contains 'rabbit-cage/commands'"; else fail_t 4 ".claude/commands target '$_target' does not contain 'rabbit-cage/commands'"; fi

# t5: .claude/hooks is a symlink and resolves to an existing path
if [ -L "$CLAUDE_DIR/hooks" ] && [ -e "$(readlink -f "$CLAUDE_DIR/hooks" 2>/dev/null)" ]; then ok 5 ".claude/hooks is a symlink and resolves"; else fail_t 5 ".claude/hooks is not a symlink or does not resolve"; fi

# t6: .claude/hooks symlink target contains "rabbit-cage/hooks"
_target="$(readlink "$CLAUDE_DIR/hooks" 2>/dev/null || true)"
if echo "$_target" | grep -q "rabbit-cage/hooks"; then ok 6 ".claude/hooks target contains 'rabbit-cage/hooks'"; else fail_t 6 ".claude/hooks target '$_target' does not contain 'rabbit-cage/hooks'"; fi

# t7: .claude/skills is NOT a symlink (managed as generated directory by generate-skills-dir.sh)
if [ ! -L "$CLAUDE_DIR/skills" ]; then ok 7 ".claude/skills is not a symlink (generated directory, managed by generate-skills-dir.sh)"; else fail_t 7 ".claude/skills is still a symlink — should be a generated directory"; fi

# t8: .claude/settings.json is a symlink and resolves to an existing path
if [ -L "$CLAUDE_DIR/settings.json" ] && [ -e "$(readlink -f "$CLAUDE_DIR/settings.json" 2>/dev/null)" ]; then ok 8 ".claude/settings.json is a symlink and resolves"; else fail_t 8 ".claude/settings.json is not a symlink or does not resolve"; fi

# t9: .claude/settings.json symlink target contains "rabbit-cage/settings.json"
_target="$(readlink "$CLAUDE_DIR/settings.json" 2>/dev/null || true)"
if echo "$_target" | grep -q "rabbit-cage/settings.json"; then ok 9 ".claude/settings.json target contains 'rabbit-cage/settings.json'"; else fail_t 9 ".claude/settings.json target '$_target' does not contain 'rabbit-cage/settings.json'"; fi

# t10: .claude/policy is a symlink and resolves to an existing path
if [ -L "$CLAUDE_DIR/policy" ] && [ -e "$(readlink -f "$CLAUDE_DIR/policy" 2>/dev/null)" ]; then ok 10 ".claude/policy is a symlink and resolves"; else fail_t 10 ".claude/policy is not a symlink or does not resolve"; fi

# t11: .claude/policy symlink target contains "features/policy"
_target="$(readlink "$CLAUDE_DIR/policy" 2>/dev/null || true)"
if echo "$_target" | grep -q "features/policy"; then ok 11 ".claude/policy target contains 'features/policy'"; else fail_t 11 ".claude/policy target '$_target' does not contain 'features/policy'"; fi

# t12: .claude/contract is a symlink and resolves to an existing path
if [ -L "$CLAUDE_DIR/contract" ] && [ -e "$(readlink -f "$CLAUDE_DIR/contract" 2>/dev/null)" ]; then ok 12 ".claude/contract is a symlink and resolves"; else fail_t 12 ".claude/contract is not a symlink or does not resolve"; fi

# t13: .claude/contract symlink target contains "features/contract"
_target="$(readlink "$CLAUDE_DIR/contract" 2>/dev/null || true)"
if echo "$_target" | grep -q "features/contract"; then ok 13 ".claude/contract target contains 'features/contract'"; else fail_t 13 ".claude/contract target '$_target' does not contain 'features/contract'"; fi

# t14: CLAUDE.md at repo root is a regular file (generated, not a symlink) with inline policy
if [ -f "$REPO_ROOT/CLAUDE.md" ] && [ ! -L "$REPO_ROOT/CLAUDE.md" ] && grep -q 'rabbit-policy-start' "$REPO_ROOT/CLAUDE.md" 2>/dev/null; then
    ok 14 "CLAUDE.md is a generated regular file containing inline policy"
else
    fail_t 14 "CLAUDE.md is missing, is still a symlink, or lacks rabbit-policy-start marker"
fi

# t15: README.md at repo root is a symlink targeting rabbit-cage and resolves
_target="$(readlink "$REPO_ROOT/README.md" 2>/dev/null || true)"
if [ -L "$REPO_ROOT/README.md" ] && echo "$_target" | grep -q "rabbit-cage" && [ -e "$(readlink -f "$REPO_ROOT/README.md" 2>/dev/null)" ]; then
    ok 15 "README.md at repo root targets rabbit-cage and resolves"
else
    fail_t 15 "README.md at repo root target '$_target' does not target rabbit-cage or does not resolve"
fi

# t16: install.sh at repo root is a symlink targeting rabbit-cage and resolves
_target="$(readlink "$REPO_ROOT/install.sh" 2>/dev/null || true)"
if [ -L "$REPO_ROOT/install.sh" ] && echo "$_target" | grep -q "rabbit-cage" && [ -e "$(readlink -f "$REPO_ROOT/install.sh" 2>/dev/null)" ]; then
    ok 16 "install.sh at repo root targets rabbit-cage and resolves"
else
    fail_t 16 "install.sh at repo root target '$_target' does not target rabbit-cage or does not resolve"
fi

# t17: .claude/agents does NOT exist as a symlink (dangling agents symlink must be removed from git)
if [ ! -L "$CLAUDE_DIR/agents" ]; then ok 17 ".claude/agents is not a symlink (removed from git)"; else fail_t 17 ".claude/agents still exists as a symlink — must be removed from git tracking"; fi

# t18: feature.json surface does NOT contain an 'agents' key (vestigial key must be removed)
_feature_json="$REPO_ROOT/.claude/features/rabbit-cage/feature.json"
if python3 -c "import json,sys; d=json.load(open('$_feature_json')); sys.exit(0 if 'agents' not in d.get('surface',{}) else 1)" 2>/dev/null; then
    ok 18 "feature.json surface has no 'agents' key"
else
    fail_t 18 "feature.json surface still has an 'agents' key — must be removed"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
