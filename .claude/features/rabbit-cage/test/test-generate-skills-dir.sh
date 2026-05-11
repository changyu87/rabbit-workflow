#!/usr/bin/env bash
# test-generate-skills-dir.sh
# t1: script exists and is executable
# t2: creates .claude/skills/ as a real directory (not symlink) when absent
# t3: creates correct symlink for a declared skill
# t4: removes stale symlink not in registry
# t5: --check exits 0 when skills dir is up-to-date
# t6: --check exits 1 when a symlink is missing
# t7: --check exits 1 when SKILL.md content changed (hash drift)
# t8: saves .rbt-skills-hash on default run

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GENERATE="$FEATURE_DIR/scripts/generate-skills-dir.sh"

pass=0; fail=0
ok()     { echo "  PASS t$1: $2"; pass=$((pass + 1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail + 1)); }

echo "test-generate-skills-dir.sh"

# Setup: isolated temp workspace with a fake registry and one skill
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/.claude/features/fake-feat/skills/my-skill"
printf -- '---\nname: my-skill\ndescription: A test skill\n---\ncontent\n' \
  > "$WORK/.claude/features/fake-feat/skills/my-skill/SKILL.md"
printf '{"surface": {"skills": ["my-skill"]}}\n' \
  > "$WORK/.claude/features/fake-feat/feature.json"
printf '{"features": {"fake-feat": {}}}\n' \
  > "$WORK/.claude/features/registry.json"
git -C "$WORK" init -q
git -C "$WORK" commit --allow-empty -q -m "init"

# t1: script exists and is executable
if [ -f "$GENERATE" ] && [ -x "$GENERATE" ]; then
  ok 1 "generate-skills-dir.sh exists and is executable"
else
  fail_t 1 "generate-skills-dir.sh missing or not executable at $GENERATE"
fi

# t2: creates .claude/skills/ as a real directory
bash "$GENERATE" "$WORK" >/dev/null 2>&1 || true
if [ -d "$WORK/.claude/skills" ] && [ ! -L "$WORK/.claude/skills" ]; then
  ok 2 "creates .claude/skills/ as a real directory"
else
  fail_t 2 ".claude/skills not a real directory after generation"
fi

# t3: creates correct symlink for declared skill
LINK="$WORK/.claude/skills/my-skill"
TARGET="$(readlink "$LINK" 2>/dev/null || true)"
if [ -L "$LINK" ] && echo "$TARGET" | grep -q "fake-feat/skills/my-skill"; then
  ok 3 "creates correct symlink for 'my-skill'"
else
  fail_t 3 "link='$LINK' target='$TARGET'"
fi

# t4: removes stale symlink not in registry
ln -s /tmp/nonexistent "$WORK/.claude/skills/stale-skill"
bash "$GENERATE" "$WORK" >/dev/null 2>&1 || true
if [ ! -e "$WORK/.claude/skills/stale-skill" ] && [ ! -L "$WORK/.claude/skills/stale-skill" ]; then
  ok 4 "removes stale symlink not in registry"
else
  fail_t 4 "stale symlink still present after regeneration"
fi

# t5: --check exits 0 when up-to-date
bash "$GENERATE" "$WORK" >/dev/null 2>&1  # fresh state + hash
if bash "$GENERATE" --check "$WORK" >/dev/null 2>&1; then
  ok 5 "--check exits 0 when skills dir is up-to-date"
else
  fail_t 5 "--check exited non-zero on a clean state"
fi

# t6: --check exits 1 when a symlink is missing
rm "$WORK/.claude/skills/my-skill"
if ! bash "$GENERATE" --check "$WORK" >/dev/null 2>&1; then
  ok 6 "--check exits 1 when a symlink is missing"
else
  fail_t 6 "--check did not detect missing symlink"
fi

# t7: --check exits 1 when SKILL.md content changed (hash drift)
bash "$GENERATE" "$WORK" >/dev/null 2>&1  # restore + save fresh hash
echo "changed content" >> "$WORK/.claude/features/fake-feat/skills/my-skill/SKILL.md"
if ! bash "$GENERATE" --check "$WORK" >/dev/null 2>&1; then
  ok 7 "--check exits 1 when SKILL.md content changed"
else
  fail_t 7 "--check did not detect content change (hash drift)"
fi

# t8: saves .rbt-skills-hash on default run
bash "$GENERATE" "$WORK" >/dev/null 2>&1
if [ -f "$WORK/.rbt-skills-hash" ]; then
  ok 8 "saves .rbt-skills-hash on default run"
else
  fail_t 8 ".rbt-skills-hash not found at $WORK after default run"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
