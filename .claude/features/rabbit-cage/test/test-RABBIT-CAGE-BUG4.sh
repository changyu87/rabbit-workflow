#!/usr/bin/env bash
# test-RABBIT-CAGE-BUG4.sh
# Tests for RABBIT-CAGE-BUG-4: build-targets.py writes .rabbit-skills-updated
# unconditionally on every shutil.copy2 of a SKILL.md target, even when source
# and destination content are identical.
#
# Fix: before copying, compare sha256(source) to sha256(destination); only
# write the .rabbit-skills-updated marker when content actually differs (or
# destination is absent).
#
# Spec invariant 24(a) (tightened): build.sh writes .rabbit-skills-updated at
# the repo root ONLY when it copies a SKILL.md target whose content actually
# changed (sha256 differs or destination absent). A no-op copy where source
# and destination sha256 are identical does NOT write the marker.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
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
    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py" \
       "$d/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py"
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

echo "test-RABBIT-CAGE-BUG4.sh"
echo ""

TMPROOT=""
trap 'rm -rf "$TMPROOT"' EXIT

# ---------------------------------------------------------------------------
# Common setup: a SKILL.md source and a contract that copies it.
# ---------------------------------------------------------------------------
TMPROOT="$(make_build_repo)"
mkdir -p "$TMPROOT/.claude/features/test-skill/skills/test-skill"
SRC="$TMPROOT/.claude/features/test-skill/skills/test-skill/SKILL.md"
DEST="$TMPROOT/.claude/skills/test-skill/SKILL.md"
MARKER="$TMPROOT/.rabbit-skills-updated"
printf '# Test skill v1\nbody\n' > "$SRC"
make_contract "$TMPROOT" '[{"name":"skills/test-skill/SKILL.md","type":"copy-file","source":".claude/features/test-skill/skills/test-skill/SKILL.md","destination":".claude/skills/test-skill/SKILL.md"}]'

# ---------------------------------------------------------------------------
# t1: destination absent → marker MUST be written (first build)
# ---------------------------------------------------------------------------
echo "=== t1: destination absent → marker IS written ==="
rm -f "$MARKER"
rm -f "$DEST"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
if [ -f "$MARKER" ]; then
    ok "marker written when destination did not exist"
else
    fail_t "marker NOT written when destination did not exist (first build must mark)"
fi

# ---------------------------------------------------------------------------
# t2: destination exists with identical content → marker must NOT be written
# ---------------------------------------------------------------------------
echo "=== t2: destination identical to source → marker NOT written ==="
# First build to create destination matching source.
rm -f "$MARKER"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
# Now destination exists and equals source. Second build should be a no-op.
rm -f "$MARKER"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
if [ -f "$MARKER" ]; then
    fail_t "marker WAS written on no-op build (source == destination); BUG-4 not fixed"
else
    ok "marker NOT written when source and destination are byte-identical"
fi

# ---------------------------------------------------------------------------
# t3: destination exists but content differs → marker MUST be written
# ---------------------------------------------------------------------------
echo "=== t3: destination differs from source → marker IS written ==="
# Modify the source to make it differ from the existing destination.
printf '# Test skill v2\nbody changed\n' > "$SRC"
rm -f "$MARKER"
bash "$BUILD_SH" "$TMPROOT" >/dev/null 2>&1 || true
if [ -f "$MARKER" ]; then
    ok "marker written when source content changed"
else
    fail_t "marker NOT written when source content actually changed"
fi

echo ""
echo "Total: $TOTAL  Failures: $FAILURES"
[ "$FAILURES" -eq 0 ] || exit 1
exit 0
