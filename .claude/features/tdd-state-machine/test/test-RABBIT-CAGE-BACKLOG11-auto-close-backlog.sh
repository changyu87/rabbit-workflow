#!/bin/bash
# test-RABBIT-CAGE-BACKLOG11-auto-close-backlog.sh
# Verify that transitioning a feature to test-green auto-closes in-progress backlog items.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TDD_STEP="$FEATURE_DIR/scripts/tdd-step.sh"
BACKLOG_STATUS_SH="$(cd "$FEATURE_DIR/../rabbit-backlog/scripts" && pwd)/backlog-item-status.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok()   { echo "  ok   $*"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build a mirror repo layout with:
#   - git repo at MIRROR_BASE
#   - feature at MIRROR_BASE/.claude/features/my-feat/
#   - backlog items at MIRROR_BASE/.claude/backlogs/my-feat/<item>/item.json
#   - stub contract/scripts/rebuild-registry.sh (no-op)
#   - real backlog-item-status.sh symlinked in place
setup_mirror() {
  local mirror_base="$1" feat_name="$2" feat_state="$3"

  local mirror_tdd_scripts="$mirror_base/.claude/features/tdd-state-machine/scripts"
  local mirror_contract_scripts="$mirror_base/.claude/features/contract/scripts"
  local mirror_features="$mirror_base/.claude/features"
  local mirror_feat="$mirror_features/$feat_name"
  local mirror_backlog_scripts="$mirror_base/.claude/features/rabbit-backlog/scripts"

  mkdir -p "$mirror_tdd_scripts" "$mirror_contract_scripts" "$mirror_feat" "$mirror_backlog_scripts"

  # Init git repo so backlog-item-status.sh can commit
  git init "$mirror_base" >/dev/null 2>&1
  git -C "$mirror_base" config user.email "test@test.com"
  git -C "$mirror_base" config user.name "Test"
  git -C "$mirror_base" commit --allow-empty -m "init" >/dev/null 2>&1

  # Copy tdd-step.sh into mirror
  cp "$TDD_STEP" "$mirror_tdd_scripts/tdd-step.sh"
  chmod +x "$mirror_tdd_scripts/tdd-step.sh"

  # Copy backlog-item-status.sh into mirror
  cp "$BACKLOG_STATUS_SH" "$mirror_backlog_scripts/backlog-item-status.sh"
  chmod +x "$mirror_backlog_scripts/backlog-item-status.sh"

  # Stub no-op rebuild-registry.sh
  cat > "$mirror_contract_scripts/rebuild-registry.sh" <<'STUB'
#!/bin/bash
exit 0
STUB
  chmod +x "$mirror_contract_scripts/rebuild-registry.sh"

  # Write feature.json
  cat > "$mirror_feat/feature.json" <<JSON
{
  "name": "$feat_name",
  "version": "0.1.0",
  "owner": "test",
  "tdd_state": "$feat_state"
}
JSON

  echo "$mirror_feat"
}

make_backlog_item() {
  local mirror_base="$1" feat_name="$2" item_name="$3" status="$4"
  local item_dir="$mirror_base/.claude/backlogs/$feat_name/$item_name"
  mkdir -p "$item_dir"
  cat > "$item_dir/item.json" <<JSON
{
  "name": "$item_name",
  "title": "Test item",
  "status": "$status",
  "priority": "medium",
  "description": "fixture",
  "owner": "test",
  "filed": "2026-05-11T00:00:00Z",
  "filed_by": "test",
  "closed": null,
  "history": [
    { "ts": "2026-05-11T00:00:00Z", "actor": "test", "action": "opened", "note": "init" }
  ]
}
JSON
  echo "$item_dir"
}

# ab1: in-progress backlog item gets auto-closed on test-green transition.
ab1() {
  local mirror_base="$TMPROOT/ab1"
  local feat_dir
  feat_dir="$(setup_mirror "$mirror_base" "my-feat" "impl")"

  local item_dir
  item_dir="$(make_backlog_item "$mirror_base" "my-feat" "MY-FEAT-BACKLOG-1" "in-progress")"

  RABBIT_ROOT="$mirror_base" "$mirror_base/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
    transition "$feat_dir" test-green >"$TMPROOT/ab1.out" 2>"$TMPROOT/ab1.err"
  local rc=$?

  local status
  status="$(jq -r '.status' "$item_dir/item.json" 2>/dev/null)"

  [ "$rc" = "0" ] && [ "$status" = "implemented" ] \
    && ok "ab1: in-progress backlog item auto-closed to implemented on test-green" \
    || ko "ab1: rc=$rc item_status=$status stderr=$(cat "$TMPROOT/ab1.err")"
}

# ab2: open backlog item is NOT touched (only in-progress items are closed).
ab2() {
  local mirror_base="$TMPROOT/ab2"
  local feat_dir
  feat_dir="$(setup_mirror "$mirror_base" "my-feat2" "impl")"

  local item_dir
  item_dir="$(make_backlog_item "$mirror_base" "my-feat2" "MY-FEAT2-BACKLOG-1" "open")"

  RABBIT_ROOT="$mirror_base" "$mirror_base/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
    transition "$feat_dir" test-green >"$TMPROOT/ab2.out" 2>"$TMPROOT/ab2.err"
  local rc=$?

  local status
  status="$(jq -r '.status' "$item_dir/item.json" 2>/dev/null)"

  [ "$rc" = "0" ] && [ "$status" = "open" ] \
    && ok "ab2: open backlog item not touched on test-green" \
    || ko "ab2: rc=$rc item_status=$status stderr=$(cat "$TMPROOT/ab2.err")"
}

# ab3: no backlog dir — transition still succeeds (best-effort).
ab3() {
  local mirror_base="$TMPROOT/ab3"
  local feat_dir
  feat_dir="$(setup_mirror "$mirror_base" "my-feat3" "impl")"
  # No backlog dir created

  RABBIT_ROOT="$mirror_base" "$mirror_base/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
    transition "$feat_dir" test-green >"$TMPROOT/ab3.out" 2>"$TMPROOT/ab3.err"
  local rc=$?

  [ "$rc" = "0" ] \
    && ok "ab3: test-green transition succeeds when no backlog dir exists" \
    || ko "ab3: rc=$rc stderr=$(cat "$TMPROOT/ab3.err")"
}

# ab4: multiple in-progress items — all get auto-closed.
ab4() {
  local mirror_base="$TMPROOT/ab4"
  local feat_dir
  feat_dir="$(setup_mirror "$mirror_base" "my-feat4" "impl")"

  local item1 item2
  item1="$(make_backlog_item "$mirror_base" "my-feat4" "MY-FEAT4-BACKLOG-1" "in-progress")"
  item2="$(make_backlog_item "$mirror_base" "my-feat4" "MY-FEAT4-BACKLOG-2" "in-progress")"

  RABBIT_ROOT="$mirror_base" "$mirror_base/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
    transition "$feat_dir" test-green >"$TMPROOT/ab4.out" 2>"$TMPROOT/ab4.err"
  local rc=$?

  local s1 s2
  s1="$(jq -r '.status' "$item1/item.json" 2>/dev/null)"
  s2="$(jq -r '.status' "$item2/item.json" 2>/dev/null)"

  [ "$rc" = "0" ] && [ "$s1" = "implemented" ] && [ "$s2" = "implemented" ] \
    && ok "ab4: multiple in-progress items all auto-closed on test-green" \
    || ko "ab4: rc=$rc s1=$s1 s2=$s2 stderr=$(cat "$TMPROOT/ab4.err")"
}

# ab5: --force path also auto-closes in-progress backlog items.
ab5() {
  local mirror_base="$TMPROOT/ab5"
  local feat_dir
  feat_dir="$(setup_mirror "$mirror_base" "my-feat5" "spec")"

  local item_dir
  item_dir="$(make_backlog_item "$mirror_base" "my-feat5" "MY-FEAT5-BACKLOG-1" "in-progress")"

  RABBIT_ROOT="$mirror_base" "$mirror_base/.claude/features/tdd-state-machine/scripts/tdd-step.sh" \
    transition "$feat_dir" test-green --force >"$TMPROOT/ab5.out" 2>"$TMPROOT/ab5.err"
  local rc=$?

  local status
  status="$(jq -r '.status' "$item_dir/item.json" 2>/dev/null)"

  [ "$rc" = "0" ] && [ "$status" = "implemented" ] \
    && ok "ab5: in-progress backlog item auto-closed on --force test-green" \
    || ko "ab5: rc=$rc item_status=$status stderr=$(cat "$TMPROOT/ab5.err")"
}

echo "running auto-close backlog tests against $TDD_STEP"
ab1; ab2; ab3; ab4; ab5
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
