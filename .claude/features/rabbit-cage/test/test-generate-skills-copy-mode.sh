#!/usr/bin/env bash
# test-generate-skills-copy-mode.sh
# Tests for the new copy-based generate-skills-dir.sh behavior.
#
# Spec invariants tested:
# t1: default mode copies skill dirs (cp -rp), NOT symlinks;
#     .claude/skills/<name> is a real directory (not a symlink) containing SKILL.md.
# t2: copy is independent of source; modifying source SKILL.md does NOT
#     change the copy (confirms cp, not symlink).
# t3: --check detects content drift: source SKILL.md sha256 != copy SKILL.md sha256 -> exit 1.
# t4: --check exits 0 when source and copy sha256 match (clean state).
# t5: --check detects missing copy (skill in feature.json but no dir in .claude/skills/) -> exit 1.
# t6: --check detects stale copy (dir in .claude/skills/ with no feature.json entry) -> exit 1.
# t7: .rbt-skills-hash is NOT created or written in default mode.
# t8: feature.json surface.skills does NOT contain "rabbit-feature-touch".
#
# All tests MUST FAIL before implementation (current script creates symlinks and
# writes .rbt-skills-hash). They turn green only after the new spec is implemented.
#
# R3-compliant: no `read` or `select`; all temp dirs cleaned on all exit paths.

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GENERATE="$FEATURE_DIR/scripts/generate-skills-dir.sh"
FEATURE_JSON="$FEATURE_DIR/feature.json"

pass=0; fail=0

ok()     { echo "  PASS t$1: $2"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail + 1)); }

echo "test-generate-skills-copy-mode.sh"

# ---------------------------------------------------------------------------
# Shared temp workspace setup
# ---------------------------------------------------------------------------
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Minimal repo structure: one feature with one skill
mkdir -p "$WORK/.claude/features/fake-feat/skills/my-skill"
printf '%s\n' '---' 'name: my-skill' 'description: A test skill' '---' 'content line 1' \
  > "$WORK/.claude/features/fake-feat/skills/my-skill/SKILL.md"
printf '{"surface": {"skills": ["my-skill"]}}\n' \
  > "$WORK/.claude/features/fake-feat/feature.json"
printf '{"features": {"fake-feat": {}}}\n' \
  > "$WORK/.claude/features/registry.json"
git -C "$WORK" init -q
git -C "$WORK" commit --allow-empty -q -m "init"

# ---------------------------------------------------------------------------
# t1: default mode produces a real directory (not a symlink) containing SKILL.md
# ---------------------------------------------------------------------------
bash "$GENERATE" "$WORK" >/dev/null 2>&1 || true

COPY_DIR="$WORK/.claude/skills/my-skill"
if [ -d "$COPY_DIR" ] && [ ! -L "$COPY_DIR" ] && [ -f "$COPY_DIR/SKILL.md" ]; then
  ok 1 "default mode: .claude/skills/my-skill is a real directory containing SKILL.md"
else
  fail_t 1 "default mode: expected real directory at $COPY_DIR containing SKILL.md; is_dir=$([ -d "$COPY_DIR" ] && echo yes || echo no) is_link=$([ -L "$COPY_DIR" ] && echo yes || echo no) has_skill=$([ -f "$COPY_DIR/SKILL.md" ] && echo yes || echo no)"
fi

# ---------------------------------------------------------------------------
# t2: copy is independent -- modifying source does NOT change the copy
# ---------------------------------------------------------------------------
COPY_MD="$WORK/.claude/skills/my-skill/SKILL.md"
SRC_MD="$WORK/.claude/features/fake-feat/skills/my-skill/SKILL.md"

# Hash the copy before touching the source
COPY_HASH_BEFORE="$(sha256sum "$COPY_MD" 2>/dev/null | awk '{print $1}' || true)"

# Append a unique marker to the SOURCE only (not the copy path)
printf '%s\n' 'extra line appended to source only' >> "$SRC_MD"

# Re-hash the copy; if it changed, it is a symlink (or hardlink to same inode)
COPY_HASH_AFTER="$(sha256sum "$COPY_MD" 2>/dev/null | awk '{print $1}' || true)"

if [ "$COPY_HASH_BEFORE" = "$COPY_HASH_AFTER" ]; then
  ok 2 "copy is independent: modifying source SKILL.md does not change the copy"
else
  fail_t 2 "copy is NOT independent: source change propagated to copy (symlink behavior detected)"
fi

# ---------------------------------------------------------------------------
# t3: --check exits 1 when source and copy sha256 differ (content drift)
# ---------------------------------------------------------------------------
# At this point: source has extra line, copy does not.
# --check must report drift (exit 1) because sha256(source) != sha256(copy).
CHECK_DRIFT_EXIT=0
bash "$GENERATE" --check "$WORK" >/dev/null 2>&1 || CHECK_DRIFT_EXIT=$?

if [ "$CHECK_DRIFT_EXIT" -ne 0 ]; then
  ok 3 "--check exits 1 when copy sha256 differs from source sha256"
else
  fail_t 3 "--check exited 0 when source and copy sha256 differ (expected exit 1)"
fi

# ---------------------------------------------------------------------------
# t4: --check exits 0 when source and copy sha256 match (clean state)
# ---------------------------------------------------------------------------
# Re-run default mode to produce a fresh copy matching the current source
bash "$GENERATE" "$WORK" >/dev/null 2>&1 || true

CHECK_CLEAN_EXIT=0
bash "$GENERATE" --check "$WORK" >/dev/null 2>&1 || CHECK_CLEAN_EXIT=$?

if [ "$CHECK_CLEAN_EXIT" -eq 0 ]; then
  ok 4 "--check exits 0 when source and copy sha256 match"
else
  fail_t 4 "--check exited $CHECK_CLEAN_EXIT on clean state (expected exit 0)"
fi

# ---------------------------------------------------------------------------
# t5: --check exits 1 when copy is missing (skill in feature.json but no dir)
# ---------------------------------------------------------------------------
rm -rf "$COPY_DIR"

MISSING_EXIT=0
bash "$GENERATE" --check "$WORK" >/dev/null 2>&1 || MISSING_EXIT=$?

if [ "$MISSING_EXIT" -ne 0 ]; then
  ok 5 "--check exits 1 when copy is missing for a declared skill"
else
  fail_t 5 "--check exited 0 when copy dir is missing (expected exit 1)"
fi

# Restore the copy for t6
bash "$GENERATE" "$WORK" >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# t6: --check exits 1 when a stale copy exists (dir in skills/ not in feature.json)
# ---------------------------------------------------------------------------
# Create a real directory in .claude/skills/ that has no corresponding feature.json entry
mkdir -p "$WORK/.claude/skills/stale-skill"
printf '%s\n' 'stale content' > "$WORK/.claude/skills/stale-skill/SKILL.md"

STALE_EXIT=0
bash "$GENERATE" --check "$WORK" >/dev/null 2>&1 || STALE_EXIT=$?

if [ "$STALE_EXIT" -ne 0 ]; then
  ok 6 "--check exits 1 when a stale real directory exists in .claude/skills/"
else
  fail_t 6 "--check exited 0 with stale directory present (expected exit 1)"
fi

rm -rf "$WORK/.claude/skills/stale-skill"

# ---------------------------------------------------------------------------
# t7: .rbt-skills-hash is NOT created or written by default mode
# ---------------------------------------------------------------------------
rm -f "$WORK/.rbt-skills-hash"

bash "$GENERATE" "$WORK" >/dev/null 2>&1 || true

if [ ! -f "$WORK/.rbt-skills-hash" ]; then
  ok 7 ".rbt-skills-hash is NOT created in default mode"
else
  fail_t 7 ".rbt-skills-hash was created in default mode (must NOT exist)"
fi

# ---------------------------------------------------------------------------
# t8: feature.json surface.skills does NOT contain "rabbit-feature-touch"
# ---------------------------------------------------------------------------
CONTAINS_RFT=0
python3 - "$FEATURE_JSON" <<'PYEOF' && CONTAINS_RFT=1 || true
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
skills = data.get("surface", {}).get("skills", [])
if "rabbit-feature-touch" in skills:
    sys.exit(0)
else:
    sys.exit(1)
PYEOF

if [ "$CONTAINS_RFT" -eq 0 ]; then
  ok 8 "feature.json surface.skills does NOT contain 'rabbit-feature-touch'"
else
  fail_t 8 "feature.json surface.skills still contains 'rabbit-feature-touch' -- must be removed"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
