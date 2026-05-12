#!/bin/bash
# tdd-step.sh — read and transition the tdd_state of a feature.
#
# Usage:
#   tdd-step.sh show <feature-dir>
#   tdd-step.sh next <feature-dir>
#   tdd-step.sh transitions <feature-dir>
#   tdd-step.sh transition <feature-dir> <new-state> [--force] [--spec-no-change-reason <reason>]
#
# Exit:
#   0 success
#   1 transition denied or invalid input
#   2 invocation error

set -u

_rbt_ok()    { printf '\033[32m[rabbit] \xe2\x94\x81\xe2\x94\x81\xe2\x94\x81 %s \xe2\x94\x81\xe2\x94\x81\xe2\x94\x81\033[0m\n' "$*"; }
_rbt_alert() { printf '\033[31m[rabbit] \xe2\x94\x81\xe2\x94\x81\xe2\x94\x81 %s \xe2\x94\x81\xe2\x94\x81\xe2\x94\x81\033[0m\n' "$*" >&2; }

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"

usage() {
  cat >&2 <<EOF
usage:
  tdd-step.sh show <feature-dir>
  tdd-step.sh next <feature-dir>
  tdd-step.sh transitions <feature-dir>
  tdd-step.sh transition <feature-dir> <new-state> [--force] [--spec-no-change-reason <reason>]
EOF
}

# Forward transitions only. Anything else requires --force.
forward_next() {
  case "$1" in
    spec)        echo "spec-update" ;;
    spec-update) echo "test-red" ;;
    test-red)   echo "impl" ;;
    impl)       echo "test-green" ;;
    test-green) echo "review" ;;
    review)     echo "merged" ;;
    merged)     echo "deprecated" ;;
    deprecated) echo "" ;;        # terminal
    *)          echo "" ;;
  esac
}

is_valid_state() {
  case "$1" in
    spec|spec-update|test-red|impl|test-green|review|merged|deprecated) return 0 ;;
    *) return 1 ;;
  esac
}

read_state() {
  local dir="$1"
  [ -f "$dir/feature.json" ] || { echo "ERROR: no feature.json in $dir" >&2; return 2; }
  jq -r '.tdd_state // ""' "$dir/feature.json"
}

write_state() {
  local dir="$1" new="$2"
  local today; today="$(date +%Y-%m-%d)"
  jq --arg s "$new" --arg u "$today" '.tdd_state = $s | .updated = $u' \
    "$dir/feature.json" > "$dir/feature.json.tmp" \
    && mv "$dir/feature.json.tmp" "$dir/feature.json"
}

# auto_close_backlog: close any in-progress backlog items for a feature.
# Best-effort — never fails the caller.
auto_close_backlog() {
  local dir="$1"
  local feature_name
  feature_name="$(jq -r '.name // ""' "$dir/feature.json" 2>/dev/null)" || return 0
  [ -z "$feature_name" ] && return 0
  local backlog_dir="$REPO_ROOT/.claude/backlogs/$feature_name"
  [ -d "$backlog_dir" ] || return 0
  local backlog_status_sh="$REPO_ROOT/.claude/features/rabbit-backlog/scripts/backlog-item-status.sh"
  [ -f "$backlog_status_sh" ] || return 0
  local fix_commit
  fix_commit="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null)" || fix_commit="HEAD"
  local item_dir
  for item_dir in "$backlog_dir"/*/; do
    [ -f "$item_dir/item.json" ] || continue
    local status
    status="$(jq -r '.status // ""' "$item_dir/item.json" 2>/dev/null)" || continue
    [ "$status" = "in-progress" ] || continue
    bash "$backlog_status_sh" set "$item_dir" implemented \
      --reason "auto-closed by tdd-step.sh test-green" \
      --fix-commits "$fix_commit" 2>/dev/null || true
  done
}

cmd="${1:-}"; shift || true

case "$cmd" in
  show)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    s=$(read_state "$dir") || exit $?
    echo "$s"
    ;;
  next)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    s=$(read_state "$dir") || exit $?
    n=$(forward_next "$s")
    [ -z "$n" ] && { echo "ERROR: $s is terminal, no forward state" >&2; exit 1; }
    echo "$n"
    ;;
  transitions)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    s=$(read_state "$dir") || exit $?
    n=$(forward_next "$s")
    if [ -n "$n" ]; then
      echo "$n"
    else
      echo "(terminal)"
    fi
    ;;
  transition)
    dir="${1:-}"; new="${2:-}"
    [ -z "$dir" ] || [ -z "$new" ] && { usage; exit 2; }
    shift 2 || true
    FORCE=0
    SPEC_NO_CHANGE_REASON=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --force) FORCE=1; shift ;;
        --spec-no-change-reason)
          [ -z "${2:-}" ] && { echo "ERROR: --spec-no-change-reason requires a non-empty reason" >&2; exit 2; }
          SPEC_NO_CHANGE_REASON="$2"; shift 2 ;;
        *) echo "ERROR: unknown flag '$1'" >&2; exit 2 ;;
      esac
    done
    is_valid_state "$new" || { echo "ERROR: '$new' is not a valid tdd_state" >&2; exit 1; }
    cur=$(read_state "$dir") || exit $?
    expected=$(forward_next "$cur")
    # Enforcement gate: spec-update → test-red requires spec change or documented reason
    if [ "$cur" = "spec-update" ] && [ "$new" = "test-red" ]; then
      if [ -n "$SPEC_NO_CHANGE_REASON" ]; then
        : # Reason documented — allowed
      else
        SPEC_DIFF="$(git -C "$REPO_ROOT" diff HEAD -- "$dir/docs/spec/" 2>/dev/null || true)"
        if [ -z "$SPEC_DIFF" ]; then
          echo "ERROR: spec-update -> test-red requires spec changes (git diff) or --spec-no-change-reason <reason>" >&2
          exit 1
        fi
      fi
    fi
    if [ "$cur" = "deprecated" ]; then
      echo "ERROR: '$cur' is terminal; cannot transition (even with --force)" >&2
      exit 1
    fi
    if [ "$new" = "$expected" ]; then
      write_state "$dir" "$new"
      # Post-transition hooks for test-green.
      if [ "$new" = "test-green" ]; then
        # Run enforcement checks (contract/scripts/enforcement/).
        ENFORCEMENT_DIR="$REPO_ROOT/.claude/features/contract/scripts/enforcement"
        if [ -d "$ENFORCEMENT_DIR" ]; then
          # R3: tests must be non-interactive
          if [ -f "$ENFORCEMENT_DIR/check-tests-non-interactive.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-tests-non-interactive.sh" "$dir" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: R3 check failed for $dir — tests may have interactive constructs"
            }
          fi
          # R6: sentinel check on any dispatch scripts in feature
          if [ -f "$ENFORCEMENT_DIR/check-sentinel.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-sentinel.sh" "$dir" >/dev/null 2>&1 || true
          fi
          # Naming convention check
          if [ -f "$ENFORCEMENT_DIR/check-naming.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-naming.sh" "$dir" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: naming check failed for $dir"
            }
          fi
          # Check 4: imports and feature paths resolve
          if [ -f "$ENFORCEMENT_DIR/check-imports-resolve.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-imports-resolve.sh" "$dir" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: R-import-resolve check failed for $dir"
            }
          fi
          # Check 5: symlinks under .claude/ resolve
          if [ -f "$ENFORCEMENT_DIR/check-symlinks-resolve.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-symlinks-resolve.sh" "$REPO_ROOT" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: symlink-resolve check failed"
            }
          fi
          # Check 6: template-schema-producer consistency
          if [ -f "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.sh" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: template-schema-producer consistency check failed"
            }
          fi
        fi
        FEATURES_DIR="$(dirname "$dir")"
        REBUILD_SH="$REPO_ROOT/.claude/features/contract/scripts/rebuild-registry.sh"
        if [ -f "$REBUILD_SH" ]; then
          bash "$REBUILD_SH" "$FEATURES_DIR" >/dev/null 2>&1 || true
        fi
        # If a project-map.json exists two levels up, consolidate the project map.
        PROJECT_MAP="$(dirname "$FEATURES_DIR")/project-map.json"
        if [ -f "$PROJECT_MAP" ]; then
          PROJECT_NAME="$(basename "$(dirname "$FEATURES_DIR")")"
          ONBOARD_SH="$REPO_ROOT/.claude/features/rabbit-cage/scripts/rabbit-project.sh"
          if [ -f "$ONBOARD_SH" ]; then
            bash "$ONBOARD_SH" consolidate "$PROJECT_NAME" >/dev/null 2>&1 || true
          fi
        fi
        # Spec invariant 4: auto-close in-progress backlog items.
        auto_close_backlog "$dir" || true
      fi
      _rbt_ok "$cur -> $new"
      exit 0
    fi
    if [ "$FORCE" = "1" ]; then
      write_state "$dir" "$new"
      # Post-transition hooks for test-green.
      if [ "$new" = "test-green" ]; then
        # Run enforcement checks (contract/scripts/enforcement/).
        ENFORCEMENT_DIR="$REPO_ROOT/.claude/features/contract/scripts/enforcement"
        if [ -d "$ENFORCEMENT_DIR" ]; then
          # R3: tests must be non-interactive
          if [ -f "$ENFORCEMENT_DIR/check-tests-non-interactive.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-tests-non-interactive.sh" "$dir" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: R3 check failed for $dir — tests may have interactive constructs"
            }
          fi
          # R6: sentinel check on any dispatch scripts in feature
          if [ -f "$ENFORCEMENT_DIR/check-sentinel.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-sentinel.sh" "$dir" >/dev/null 2>&1 || true
          fi
          # Naming convention check
          if [ -f "$ENFORCEMENT_DIR/check-naming.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-naming.sh" "$dir" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: naming check failed for $dir"
            }
          fi
          # Check 4: imports and feature paths resolve
          if [ -f "$ENFORCEMENT_DIR/check-imports-resolve.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-imports-resolve.sh" "$dir" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: R-import-resolve check failed for $dir"
            }
          fi
          # Check 5: symlinks under .claude/ resolve
          if [ -f "$ENFORCEMENT_DIR/check-symlinks-resolve.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-symlinks-resolve.sh" "$REPO_ROOT" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: symlink-resolve check failed"
            }
          fi
          # Check 6: template-schema-producer consistency
          if [ -f "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.sh" ]; then
            bash "$ENFORCEMENT_DIR/check-template-schema-producer-consistency.sh" >/dev/null 2>&1 || {
              _rbt_alert "WARNING: template-schema-producer consistency check failed"
            }
          fi
        fi
        FEATURES_DIR="$(dirname "$dir")"
        REBUILD_SH="$REPO_ROOT/.claude/features/contract/scripts/rebuild-registry.sh"
        if [ -f "$REBUILD_SH" ]; then
          bash "$REBUILD_SH" "$FEATURES_DIR" >/dev/null 2>&1 || true
        fi
        # If a project-map.json exists two levels up, consolidate the project map.
        PROJECT_MAP="$(dirname "$FEATURES_DIR")/project-map.json"
        if [ -f "$PROJECT_MAP" ]; then
          PROJECT_NAME="$(basename "$(dirname "$FEATURES_DIR")")"
          ONBOARD_SH="$REPO_ROOT/.claude/features/rabbit-cage/scripts/rabbit-project.sh"
          if [ -f "$ONBOARD_SH" ]; then
            bash "$ONBOARD_SH" consolidate "$PROJECT_NAME" >/dev/null 2>&1 || true
          fi
        fi
        # Spec invariant 4: auto-close in-progress backlog items.
        auto_close_backlog "$dir" || true
      fi
      _rbt_alert "FORCED: $cur -> $new"
      _rbt_ok "$cur -> $new"
      exit 0
    fi
    echo "ERROR: $cur -> $new not allowed (forward expected: $expected). Use --force to override." >&2
    exit 1
    ;;
  ""|-h|--help|help)
    usage; [ -z "$cmd" ] && exit 2 || exit 0
    ;;
  *)
    echo "ERROR: unknown subcommand '$cmd'" >&2
    usage; exit 2
    ;;
esac
