#!/usr/bin/env bash
# backlog-item-status.sh — read or transition the status of a backlog item.
#
# Usage:
#   backlog-item-status.sh get <item-dir>
#   backlog-item-status.sh set <item-dir> <new-status> --reason <text> [--fix-commits <sha>] [--actor <name>]
#
# Valid status values: open | in-progress | implemented | refused | reopened
#
# Allowed transitions:
#   open        -> in-progress  (--reason required)
#   open        -> refused      (--reason required)
#   in-progress -> implemented  (--reason required, --fix-commits required)
#   in-progress -> refused      (--reason required)
#   implemented -> reopened     (--reason required)
#   refused     -> reopened     (--reason required)
#   reopened    -> in-progress  (--reason required)
#   reopened    -> refused      (--reason required)
#
# Invalid statuses: done, cancelled — rejected with exit 1
#
# Exit: 0=ok  1=error  2=usage

set -u

usage() {
  cat >&2 <<EOF
usage:
  backlog-item-status.sh get <item-dir>
  backlog-item-status.sh set <item-dir> <new-status> --reason <text> [--fix-commits <sha>] [--actor <name>]
EOF
}

cmd="${1:-}"
shift || true

case "$cmd" in
  get)
    dir="${1:-}"
    [ -z "$dir" ] && { usage; exit 2; }
    [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" >&2; exit 1; }
    [ -f "$dir/item.json" ] || { echo "ERROR: missing $dir/item.json" >&2; exit 1; }
    jq -r '.status' "$dir/item.json"
    ;;

  set)
    dir="${1:-}"; new="${2:-}"; reason=""; fix_commits=""; tdd_report_path=""; actor="${USER:-unknown}"
    shift 2 2>/dev/null || true

    while [ $# -gt 0 ]; do
      case "$1" in
        --reason)      reason="$2";           shift 2 ;;
        --fix-commits) fix_commits="$2";      shift 2 ;;
        --tdd-report)
          [ -z "${2:-}" ] && { echo "ERROR: --tdd-report requires a path" >&2; exit 2; }
          tdd_report_path="$2"; shift 2 ;;
        --actor)       actor="$2";            shift 2 ;;
        *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2 ;;
      esac
    done

    [ -z "$dir" ] || [ -z "$new" ] && { usage; exit 2; }
    [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" >&2; exit 1; }
    [ -f "$dir/item.json" ] || { echo "ERROR: missing $dir/item.json" >&2; exit 1; }

    # Enforce --reason is required
    if [ -z "$reason" ]; then
      echo "ERROR: --reason is required" >&2
      exit 1
    fi

    # Validate new status
    case "$new" in
      open|in-progress|implemented|refused|reopened) ;;
      done|cancelled) echo "ERROR: invalid status '$new' — 'done' and 'cancelled' are no longer valid; use 'implemented' or 'refused'" >&2; exit 1 ;;
      *) echo "ERROR: invalid status '$new' (allowed: open|in-progress|implemented|refused|reopened)" >&2; exit 1 ;;
    esac

    # Reject --fix-commits on non-implemented transitions
    if [ -n "$fix_commits" ] && [ "$new" != "implemented" ]; then
      echo "ERROR: --fix-commits is only valid when transitioning to 'implemented'" >&2
      exit 1
    fi

    # Require --fix-commits when transitioning to implemented
    if [ "$new" = "implemented" ] && [ -z "$fix_commits" ]; then
      echo "ERROR: --fix-commits is required when transitioning to 'implemented'" >&2
      exit 1
    fi

    cur="$(jq -r '.status' "$dir/item.json")"

    # Same status: no-op
    if [ "$cur" = "$new" ]; then
      echo "no-op: already $cur"
      exit 0
    fi

    # Validate allowed transitions
    allowed=0
    case "${cur}->${new}" in
      "open->in-progress")       allowed=1 ;;
      "open->refused")           allowed=1 ;;
      "in-progress->implemented") allowed=1 ;;
      "in-progress->refused")    allowed=1 ;;
      "implemented->reopened")   allowed=1 ;;
      "refused->reopened")       allowed=1 ;;
      "reopened->in-progress")   allowed=1 ;;
      "reopened->refused")       allowed=1 ;;
    esac

    if [ "$allowed" -ne 1 ]; then
      echo "ERROR: transition '$cur' -> '$new' is not allowed" >&2
      exit 1
    fi

    TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # Build history entry — include fix_commits and tdd_report when transitioning to implemented
    if [ "$new" = "implemented" ]; then
      tdd_report_json="null"
      if [ -n "$tdd_report_path" ] && [ -f "$tdd_report_path" ]; then
        tdd_report_json=$(cat "$tdd_report_path")
      fi
      jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$reason" --arg fc "$fix_commits" --argjson rpt "$tdd_report_json" \
        '.status = $s
         | .closed = $ts
         | .history += [{ ts: $ts, actor: $actor, action: $s, note: $note, fix_commits: $fc, tdd_report: $rpt }]' \
        "$dir/item.json" > "$dir/item.json.tmp"
    elif [ "$new" = "reopened" ]; then
      jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$reason" \
        '.status = $s
         | .closed = null
         | .history += [{ ts: $ts, actor: $actor, action: $s, note: $note }]' \
        "$dir/item.json" > "$dir/item.json.tmp"
    else
      jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$reason" \
        '.status = $s
         | .history += [{ ts: $ts, actor: $actor, action: $s, note: $note }]' \
        "$dir/item.json" > "$dir/item.json.tmp"
    fi

    mv "$dir/item.json.tmp" "$dir/item.json"

    # Git commit after successful transition — silent on failure
    REASON_SUMMARY="${reason:0:60}"
    NAME="$(jq -r '.name // "unknown"' "$dir/item.json" 2>/dev/null)"
    REPO_ROOT="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || true
    if [ -n "$REPO_ROOT" ]; then
      git -C "$REPO_ROOT" add "$dir/item.json" 2>/dev/null && \
        git -C "$REPO_ROOT" commit -m "backlog: $NAME $cur -> $new ($REASON_SUMMARY)" 2>/dev/null || true
    fi

    echo "$cur -> $new"
    ;;

  ""|-h|--help|help)
    usage; [ -z "$cmd" ] && exit 2 || exit 0
    ;;

  *)
    echo "ERROR: unknown subcommand '$cmd'" >&2
    usage; exit 2
    ;;
esac
