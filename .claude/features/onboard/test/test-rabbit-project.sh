#!/bin/bash
# test-rabbit-project.sh — functional tests for rabbit-project.sh.
#
# Runs entirely in a temp directory that mirrors the expected repo layout.
# REPO_ROOT is overridden to point at the temp dir.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REAL_SCRIPT="$(cd "$SCRIPT_DIR/.." && pwd)/scripts/rabbit-project.sh"
REAL_CONTRACT_TEMPLATES="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}/.claude/features/contract/templates"

PASS=0; FAIL=0
ok()   { echo "  ok   $*"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Create a minimal temp repo structure:
# TMPROOT/
#   .claude/features/contract/templates/  (symlinked from real templates)
#   .claude/features/onboard/scripts/rabbit-project.sh  (copy of real script)
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

mkdir -p "$TMPROOT/.claude/features/contract"
cp -r "$REAL_CONTRACT_TEMPLATES" "$TMPROOT/.claude/features/contract/templates"
mkdir -p "$TMPROOT/.claude/features/onboard/scripts"
cp "$REAL_SCRIPT" "$TMPROOT/.claude/features/onboard/scripts/rabbit-project.sh"
chmod +x "$TMPROOT/.claude/features/onboard/scripts/rabbit-project.sh"

RUN() { RABBIT_ROOT="$TMPROOT" "$TMPROOT/.claude/features/onboard/scripts/rabbit-project.sh" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# t1: init creates expected directories and files.
t1() {
  local rc; rc=$(RUN init test-proj)
  local proj="$TMPROOT/project-test-proj"
  [ "$rc" = "0" ] \
    && [ -d "$proj/features" ] \
    && [ -d "$proj/contract" ] \
    && [ -f "$proj/project-map.json" ] \
    && [ -f "$proj/features/registry.json" ] \
    && ok "t1: init creates project-test-proj/ with expected structure" \
    || ko "t1: rc=$rc proj_exists=$([ -d "$proj" ] && echo yes || echo no) stderr=$(cat "$TMPROOT/stderr")"
}

# t2: set-path updates path field in project-map.json.
t2() {
  local rc; rc=$(RUN set-path test-proj /some/path)
  local path_val
  path_val=$(python3 -c "import json; d=json.load(open('$TMPROOT/project-test-proj/project-map.json')); print(d.get('path',''))")
  [ "$rc" = "0" ] && [ "$path_val" = "/some/path" ] \
    && ok "t2: set-path updates path to /some/path" \
    || ko "t2: rc=$rc path_val=$path_val stderr=$(cat "$TMPROOT/stderr")"
}

# t3: map adds source_map entry.
t3() {
  local rc; rc=$(RUN map test-proj src/rtl/ rtl-feature)
  local feat_val
  feat_val=$(python3 -c "import json; d=json.load(open('$TMPROOT/project-test-proj/project-map.json')); print(d.get('source_map',{}).get('src/rtl/',''))")
  [ "$rc" = "0" ] && [ "$feat_val" = "rtl-feature" ] \
    && ok "t3: map adds src/rtl/ -> rtl-feature" \
    || ko "t3: rc=$rc feat_val=$feat_val stderr=$(cat "$TMPROOT/stderr")"
}

# t4: consolidate exits 0 (with warnings to stderr, but exit 0).
t4() {
  local rc; rc=$(RUN consolidate test-proj)
  [ "$rc" = "0" ] \
    && ok "t4: consolidate exits 0" \
    || ko "t4: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# t5: init again on existing project fails.
t5() {
  local rc; rc=$(RUN init test-proj)
  [ "$rc" != "0" ] \
    && ok "t5: init on existing project-test-proj fails" \
    || ko "t5: rc=$rc — should have failed"
}

# t6: set-path on nonexistent project fails.
t6() {
  local rc; rc=$(RUN set-path nonexistent /some/path)
  [ "$rc" != "0" ] \
    && ok "t6: set-path on nonexistent project fails" \
    || ko "t6: rc=$rc — should have failed"
}

# t7: set-path with non-absolute path fails.
t7() {
  local rc; rc=$(RUN set-path test-proj relative/path)
  [ "$rc" != "0" ] \
    && ok "t7: set-path with non-absolute path fails" \
    || ko "t7: rc=$rc — should have failed"
}

# t8: map on nonexistent project fails.
t8() {
  local rc; rc=$(RUN map nonexistent src/ feat)
  [ "$rc" != "0" ] \
    && ok "t8: map on nonexistent project fails" \
    || ko "t8: rc=$rc — should have failed"
}

# t9: consolidate on nonexistent project fails.
t9() {
  local rc; rc=$(RUN consolidate nonexistent)
  [ "$rc" != "0" ] \
    && ok "t9: consolidate on nonexistent project fails" \
    || ko "t9: rc=$rc — should have failed"
}

# t10: project-map.json has correct name field after init.
t10() {
  local name_val
  name_val=$(python3 -c "import json; d=json.load(open('$TMPROOT/project-test-proj/project-map.json')); print(d.get('name',''))")
  [ "$name_val" = "test-proj" ] \
    && ok "t10: project-map.json has name=test-proj" \
    || ko "t10: name_val=$name_val"
}

# t11: features/registry.json has correct owner field after init.
t11() {
  local owner_val
  owner_val=$(python3 -c "import json; d=json.load(open('$TMPROOT/project-test-proj/features/registry.json')); print(d.get('owner',''))")
  [ "$owner_val" = "test-proj team" ] \
    && ok "t11: features/registry.json has owner=test-proj team" \
    || ko "t11: owner_val=$owner_val"
}

echo "running rabbit-project tests against $REAL_SCRIPT"
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10; t11
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
