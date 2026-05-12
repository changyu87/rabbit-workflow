#!/usr/bin/env bash
# test-RABBIT-CAGE-20-untracked-skills.sh
# Tests that rbt-sync-check.sh detects untracked skill directories under
# .claude/skills/ or .claude/features/*/skills/ (RABBIT-CAGE-20).
#
# Bug: when a new skill directory is added to source AND deployed to
# .claude/skills/, generate-skills-dir.sh --check returns 0 (byte-identical),
# so no skills-updated alert is emitted. The new files can sit untracked
# in git indefinitely with no notification.
#
# Fix: rbt-sync-check.sh must additionally call git ls-files --others to
# find untracked files under .claude/skills/ or .claude/features/*/skills/
# and treat their presence as skills drift, emitting the same alert.
#
# Spec invariant: 24.
#
# R3-compliant: non-interactive, all temp dirs cleaned on EXIT.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/rbt-sync-check.sh"
GENERATE_CLAUDE_MD="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"
GENERATE_SKILLS="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"
POLICY_HEADER="$REPO_ROOT/.claude/features/rabbit-cage/policy-header.json"

FAILURES=0

ok()     { echo "  PASS t$1: $2"; }
fail_t() { echo "  FAIL t$1: $2"; FAILURES=$(( FAILURES + 1 )); }

echo "test-RABBIT-CAGE-20-untracked-skills.sh"
echo ""

# t1: rbt-sync-check.sh exists and is executable
if [ -f "$SYNC_CHECK" ] && [ -x "$SYNC_CHECK" ]; then
    ok 1 "rbt-sync-check.sh exists and is executable"
else
    fail_t 1 "rbt-sync-check.sh missing or not executable at $SYNC_CHECK"
fi

# Set up minimal temp repo with rabbit-cage layout and an untracked skill dir
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

mkdir -p "$TMPROOT/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT/.claude/features/policy"
mkdir -p "$TMPROOT/.claude/features/fake-feat/skills/new-skill"
mkdir -p "$TMPROOT/.claude/skills/new-skill"

# Minimal policy files so generate-claude-md.sh can produce output
printf '# Philosophy\nMachine First.\n'    > "$TMPROOT/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'             > "$TMPROOT/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'           > "$TMPROOT/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'     > "$TMPROOT/.claude/features/policy/workflow-rules.md"

# policy-header.json
python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
    > "$TMPROOT/.claude/features/rabbit-cage/policy-header.json"

# Copy the real generate-claude-md.sh and generate-skills-dir.sh into temp tree
cp "$GENERATE_CLAUDE_MD" "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"
cp "$GENERATE_SKILLS"    "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"

# Skill source + deployed copy (byte-identical so generate-skills-dir.sh --check returns 0)
SKILL_BODY='---
name: new-skill
description: A test skill
---
content
'
printf '%s' "$SKILL_BODY" > "$TMPROOT/.claude/features/fake-feat/skills/new-skill/SKILL.md"
printf '%s' "$SKILL_BODY" > "$TMPROOT/.claude/skills/new-skill/SKILL.md"

# feature.json declares the skill so generate-skills-dir.sh sees it as known
printf '{"surface": {"skills": ["new-skill"]}}\n' \
    > "$TMPROOT/.claude/features/fake-feat/feature.json"
printf '{"features": {"fake-feat": {}}}\n' \
    > "$TMPROOT/.claude/features/registry.json"

# Initialize git, make an initial commit that does NOT add the skill dirs.
# This leaves both .claude/features/fake-feat/skills/new-skill/ and
# .claude/skills/new-skill/ untracked.
git -C "$TMPROOT" init -q
git -C "$TMPROOT" -c user.email=t@e -c user.name=t add \
    .claude/features/policy \
    .claude/features/rabbit-cage \
    .claude/features/fake-feat/feature.json \
    .claude/features/registry.json >/dev/null 2>&1
git -C "$TMPROOT" -c user.email=t@e -c user.name=t commit -q -m "init"

# Sanity check: confirm the skill paths are untracked
UNTRACKED_OUT="$(git -C "$TMPROOT" ls-files --others --exclude-standard 2>/dev/null)"
if echo "$UNTRACKED_OUT" | grep -q 'skills/new-skill'; then
    ok 2 "pre-condition: skill dirs are untracked in temp git repo"
else
    fail_t 2 "pre-condition failed: skill dirs not reported as untracked; got: '$UNTRACKED_OUT'"
fi

# Pre-create CLAUDE.md so the hook does NOT take the first-run branch and
# does NOT take the drift branch — we want execution to reach the skills
# drift block.
EXPECTED_CLAUDE_MD="$(RABBIT_ROOT="$TMPROOT" bash "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$EXPECTED_CLAUDE_MD" > "$TMPROOT/CLAUDE.md"

# Sanity: generate-skills-dir.sh --check should currently report CLEAN
# (byte-identical source vs deployed). This is the bug — drift detection
# misses the untracked-files dimension.
SKILLS_CHECK_EXIT=0
bash "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh" \
    --check "$TMPROOT" >/dev/null 2>&1 || SKILLS_CHECK_EXIT=$?
if [ "$SKILLS_CHECK_EXIT" -eq 0 ]; then
    ok 3 "pre-condition: generate-skills-dir.sh --check reports CLEAN (byte-identical)"
else
    fail_t 3 "pre-condition: generate-skills-dir.sh --check unexpectedly reported drift (exit $SKILLS_CHECK_EXIT)"
fi

# Run the hook
sync_output=""
sync_exit=0
sync_output="$(RABBIT_ROOT="$TMPROOT" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" \
    || sync_exit=$?

# t4: hook exits 0
if [ "$sync_exit" -eq 0 ]; then
    ok 4 "rbt-sync-check.sh exits 0"
else
    fail_t 4 "rbt-sync-check.sh exited $sync_exit (expected 0); output: '$sync_output'"
fi

# t5: hook output contains a skills-updated systemMessage JSON object
# (We check for "Skills updated" — the canonical green-alert phrase.)
if echo "$sync_output" | python3 -c "
import sys, json
raw = sys.stdin.read().strip()
# Hook may emit multiple JSON objects (one per line / newline separated).
# Iterate over candidate JSON blobs and check each.
found = False
for chunk in raw.splitlines():
    chunk = chunk.strip()
    if not chunk:
        continue
    try:
        d = json.loads(chunk)
    except Exception:
        continue
    msg = d.get('systemMessage', '') or ''
    if 'Skills updated' in msg:
        found = True
        break
sys.exit(0 if found else 1)
" 2>/dev/null; then
    ok 5 "hook emitted Skills updated systemMessage when untracked skill dirs present"
else
    fail_t 5 "hook did NOT emit Skills updated systemMessage; output: '$sync_output'"
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
