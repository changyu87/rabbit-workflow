#!/usr/bin/env bash
# backlog-item-status.sh — read or transition the status of a backlog item.
#
# Usage:
#   backlog-item-status.sh get <item-dir>
#   backlog-item-status.sh set <item-dir> <new-status> [--reason <text>]
#
# Valid status values: open | in-progress | done | cancelled
#
# Allowed transitions:
#   open        -> in-progress
#   in-progress -> done
#   open        -> cancelled
#   in-progress -> cancelled
#   (any)       -> (same)     no-op, history not appended
#
# Exit: 0=ok  1=error  2=usage

set -u

usage() {
  cat >&2 <<EOF
usage:
  backlog-item-status.sh get <item-dir>
  backlog-item-status.sh set <item-dir> <new-status> [--reason <text>]
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
    dir="${1:-}"; new="${2:-}"; reason=""; actor="${USER:-unknown}"
    shift 2 2>/dev/null || true

    while [ $# -gt 0 ]; do
      case "$1" in
        --reason) reason="$2"; shift 2 ;;
        --actor)  actor="$2";  shift 2 ;;
        *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2 ;;
      esac
    done

    [ -z "$dir" ] || [ -z "$new" ] && { usage; exit 2; }
    [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" >&2; exit 1; }
    [ -f "$dir/item.json" ] || { echo "ERROR: missing $dir/item.json" >&2; exit 1; }

    # Validate new status
    case "$new" in
      open|in-progress|done|cancelled) ;;
      *) echo "ERROR: invalid status '$new' (allowed: open|in-progress|done|cancelled)" >&2; exit 1 ;;
    esac

    cur="$(jq -r '.status' "$dir/item.json")"

    # Same status: no-op
    if [ "$cur" = "$new" ]; then
      echo "no-op: already $cur"
      exit 0
    fi

    # Validate allowed transitions
    allowed=0
    case "${cur}->${new}" in
      "open->in-progress")    allowed=1 ;;
      "in-progress->done")    allowed=1 ;;
      "open->cancelled")      allowed=1 ;;
      "in-progress->cancelled") allowed=1 ;;
    esac

    if [ "$allowed" -ne 1 ]; then
      echo "ERROR: transition '$cur' -> '$new' is not allowed" >&2
      exit 1
    fi

    TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # Determine closed timestamp for terminal states
    if [ "$new" = "done" ] || [ "$new" = "cancelled" ]; then
      jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$reason" \
        '.status = $s
         | .closed = $ts
         | .history += [{ ts: $ts, actor: $actor, action: $s, note: $note }]' \
        "$dir/item.json" > "$dir/item.json.tmp"
    else
      jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$reason" \
        '.status = $s
         | .history += [{ ts: $ts, actor: $actor, action: $s, note: $note }]' \
        "$dir/item.json" > "$dir/item.json.tmp"
    fi

    mv "$dir/item.json.tmp" "$dir/item.json"
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
