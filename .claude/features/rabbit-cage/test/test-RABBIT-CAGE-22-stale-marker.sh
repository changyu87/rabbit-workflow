#!/usr/bin/env bash
# test-RABBIT-CAGE-22-stale-marker.sh
# Tests for RABBIT-CAGE-22/24: .rabbit-skills-updated marker model.
#
# Spec invariant 24 (updated by RABBIT-CAGE-24):
# (a) build.sh appends skill name to .rabbit-skills-updated for SKILL.md targets only
# (b) build.sh does NOT write marker for commands/agents/other targets
# (c) session-init.sh does NOT reference .rabbit-plugins-stale
# (d) sync-check.sh does NOT reference .rabbit-plugins-stale
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.sh"
SESSION_INIT="$REPO_ROOT/.claude/features/rabbit-cage/hooks/session-init.sh"
BUILD_SH="$REPO_ROOT/.claude/features/rabbit-cage/scripts/build.sh"

FAILURES=0
TOTAL=0

ok() { TOTAL=$(( TOTAL + 1 )); echo "  PASS t$TOTAL: $1"; }
fail_t() { TOTAL=$(( TOTAL + 1 )); FAILURES=$(( FAILURES + 1 )); echo "  FAIL t$TOTAL: $1"; }

make_build_repo() {
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

make_contract() {
    local d="$1" targets="$2"
    mkdir -p "$d/.claude/features/contract"
    python3 -c "
import json, sys
targets = json.loads(sys.argv[1])
contract = {
    'schema_version': '1.0.0',
    'owner': 'test',
    'deprecation_criterion': 'test',
    'updated': '2026-01-01',
    'targets': targets
}
print(json.dumps(contract, indent=2))
" "$targets" > "$d/.claude/features/contract/build-contract.json"
}

echo "test-RABBIT-CAGE-22-stale-marker.sh"
echo ""

TMPROOT=""
trap 'rm -rf "$TMPROOT"' EXIT

# ---------------------------------------------------------------------------
# t1: build.sh writes .rabbit-skills-updated with skill name for SKILL.md target
# ---------------------------------------------------------------------------
echo "=== t1: build.sh writes .rabbit-skills-updated for .claude/skills/*/SKILL.md target ==="
TMPROOT="$(make_build_repo)"
mkdir -p "$TMPROOT/.claude/features/test-skill/skills/test-skill"
printf '# Test skill\n' > "$TMPROOT/.claude/features/test-skill/skills/test-skill/SKILL.md"
make_contract "$TMPROOT" '[{"name":"skills/test-skill/SKILL.md","type":"copy-file","source":".claude/features/test-skill/skills/test-skill/SKILL.md","destination":".claude/skills/test-skill/SKILL.md"}]'
rm -f "$TMPROOT/.rabbit-skills-updated"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
if [ -f "$TMPROOT/.rabbit-skills-updated" ]; then
    ok "build.sh wrote .rabbit-skills-updated after copying a SKILL.md target"
else
    fail_t "build.sh did NOT write .rabbit-skills-updated after copying a SKILL.md target"
fi

# ---------------------------------------------------------------------------
# t2: .rabbit-skills-updated content is the skill name
# ---------------------------------------------------------------------------
echo "=== t2: .rabbit-skills-updated contains the skill name ==="
if [ -f "$TMPROOT/.rabbit-skills-updated" ]; then
    _content="$(cat "$TMPROOT/.rabbit-skills-updated")"
    if printf '%s' "$_content" | grep -q 'test-skill'; then
        ok ".rabbit-skills-updated contains skill name 'test-skill'"
    else
        fail_t ".rabbit-skills-updated does NOT contain 'test-skill' (content: $(printf '%q' "$_content"))"
    fi
else
    fail_t ".rabbit-skills-updated missing (covered by t1)"
fi

# ---------------------------------------------------------------------------
# t3: build.sh does NOT write .rabbit-skills-updated for commands target
# ---------------------------------------------------------------------------
echo "=== t3: build.sh does NOT write .rabbit-skills-updated for .claude/commands/ target ==="
mkdir -p "$TMPROOT/.claude/features/rabbit-cage/commands"
printf '# Test cmd\n' > "$TMPROOT/.claude/features/rabbit-cage/commands/test-cmd.md"
make_contract "$TMPROOT" '[{"name":"commands/test-cmd.md","type":"copy-file","source":".claude/features/rabbit-cage/commands/test-cmd.md","destination":".claude/commands/test-cmd.md"}]'
rm -f "$TMPROOT/.rabbit-skills-updated"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
if [ -f "$TMPROOT/.rabbit-skills-updated" ]; then
    fail_t "build.sh incorrectly wrote .rabbit-skills-updated for a commands target"
else
    ok "build.sh did NOT write .rabbit-skills-updated for a commands target"
fi

# ---------------------------------------------------------------------------
# t4: build.sh does NOT write .rabbit-skills-updated for a generic copy target
# ---------------------------------------------------------------------------
echo "=== t4: build.sh does NOT write .rabbit-skills-updated for non-skills copy target ==="
printf '# README\n' > "$TMPROOT/source-readme.md"
make_contract "$TMPROOT" '[{"name":"README.md","type":"copy-file","source":"source-readme.md","destination":"README.md"}]'
rm -f "$TMPROOT/.rabbit-skills-updated"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
if [ -f "$TMPROOT/.rabbit-skills-updated" ]; then
    fail_t "build.sh incorrectly wrote .rabbit-skills-updated for a non-skills target"
else
    ok "build.sh did NOT write .rabbit-skills-updated for a non-skills target"
fi

# ---------------------------------------------------------------------------
# t5: build.sh appends multiple skill names for multiple SKILL.md targets
# ---------------------------------------------------------------------------
echo "=== t5: build.sh appends multiple skill names for multiple SKILL.md targets ==="
mkdir -p "$TMPROOT/.claude/features/feat-a/skills/feat-a"
mkdir -p "$TMPROOT/.claude/features/feat-b/skills/feat-b"
printf '# Feat A\n' > "$TMPROOT/.claude/features/feat-a/skills/feat-a/SKILL.md"
printf '# Feat B\n' > "$TMPROOT/.claude/features/feat-b/skills/feat-b/SKILL.md"
make_contract "$TMPROOT" '[
  {"name":"skills/feat-a/SKILL.md","type":"copy-file","source":".claude/features/feat-a/skills/feat-a/SKILL.md","destination":".claude/skills/feat-a/SKILL.md"},
  {"name":"skills/feat-b/SKILL.md","type":"copy-file","source":".claude/features/feat-b/skills/feat-b/SKILL.md","destination":".claude/skills/feat-b/SKILL.md"}
]'
rm -f "$TMPROOT/.rabbit-skills-updated"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
if [ -f "$TMPROOT/.rabbit-skills-updated" ]; then
    _content="$(cat "$TMPROOT/.rabbit-skills-updated")"
    if printf '%s' "$_content" | grep -q 'feat-a' && printf '%s' "$_content" | grep -q 'feat-b'; then
        ok ".rabbit-skills-updated contains both skill names"
    else
        fail_t ".rabbit-skills-updated missing skill names (content: $(printf '%q' "$_content"))"
    fi
else
    fail_t "build.sh did NOT write .rabbit-skills-updated for multiple SKILL.md targets"
fi

# ---------------------------------------------------------------------------
# t6: session-init.sh does NOT reference .rabbit-plugins-stale
# ---------------------------------------------------------------------------
echo "=== t6: session-init.sh does NOT reference .rabbit-plugins-stale ==="
if grep -q '\.rabbit-plugins-stale' "$SESSION_INIT" 2>/dev/null; then
    fail_t "session-init.sh still references .rabbit-plugins-stale — must be removed"
else
    ok "session-init.sh has no .rabbit-plugins-stale reference"
fi

# ---------------------------------------------------------------------------
# t7: sync-check.sh does NOT reference .rabbit-plugins-stale
# ---------------------------------------------------------------------------
echo "=== t7: sync-check.sh does NOT reference .rabbit-plugins-stale ==="
if grep -q '\.rabbit-plugins-stale' "$SYNC_CHECK" 2>/dev/null; then
    fail_t "sync-check.sh still references .rabbit-plugins-stale — must be removed"
else
    ok "sync-check.sh has no .rabbit-plugins-stale reference"
fi

rm -rf "$TMPROOT" 2>/dev/null || true
trap - EXIT
echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"
[ "$FAILURES" -eq 0 ] && { echo "ALL TESTS PASSED"; exit 0; } || { echo "$FAILURES TEST(S) FAILED"; exit 1; }
