#!/bin/bash
# bug-status.sh — read or transition the status of a bug.
#
# Usage:
#   bug-status.sh get <bug-dir>
#   bug-status.sh set <bug-dir> <new-status> --note <reason>
#
# Allowed transitions:
#   open       -> closed
#   closed     -> reopened
#   reopened   -> closed
#   (any)      -> (same)   no-op, history not appended
#
# Disallowed (must use 'reopened' instead):
#   closed     -> open
#   reopened   -> open
#
# Exit: 0 success; 1 denied / invalid; 2 invocation error.

set -u

usage() {
  cat >&2 <<EOF
usage:
  bug-status.sh get <bug-dir>
  bug-status.sh set <bug-dir> <new-status> --note <reason>
EOF
}

cmd="${1:-}"; shift || true

case "$cmd" in
  get)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" >&2; exit 2; }
    [ -f "$dir/bug.json" ] || { echo "ERROR: missing $dir/bug.json" >&2; exit 2; }
    jq -r '.status' "$dir/bug.json"
    ;;
  set)
    dir="${1:-}"; new="${2:-}"; note=""; actor="${USER:-unknown}"
    shift 2 2>/dev/null || true
    skip_vet_reason=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --note)             note="$2"; shift 2 ;;
        --actor)            actor="$2"; shift 2 ;;
        --skip-vet-reason)  skip_vet_reason="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
    done
    [ -z "$dir" ] || [ -z "$new" ] && { usage; exit 2; }
    [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" >&2; exit 2; }
    [ -f "$dir/bug.json" ] || { echo "ERROR: missing $dir/bug.json" >&2; exit 2; }

    case "$new" in
      open|closed|reopened) ;;
      *) echo "ERROR: invalid status '$new' (allowed: open|closed|reopened)" >&2; exit 1 ;;
    esac

    cur=$(jq -r '.status' "$dir/bug.json")

    # Same status: no-op, exit 0 silently (no history append)
    if [ "$cur" = "$new" ]; then
      echo "no-op: already $cur"
      exit 0
    fi

    # Validate allowed transitions
    allowed=0
    case "${cur}->${new}" in
      "open->closed")     allowed=1 ;;
      "closed->reopened") allowed=1 ;;
      "reopened->closed") allowed=1 ;;
    esac
    if [ "$allowed" -ne 1 ]; then
      echo "ERROR: $cur -> $new not allowed (use 'reopened' to revive a closed bug)" >&2
      exit 1
    fi

    # Vet gate: closing requires vet-triage.json unless --skip-vet-reason provided.
    if [ "$new" = "closed" ]; then
      if [ ! -f "$dir/vet-triage.json" ] && [ -z "$skip_vet_reason" ]; then
        echo "ERROR: cannot close without vet triage. Run rabbit-vet first, or pass --skip-vet-reason if closing from an active breeder scope." >&2
        exit 1
      fi
    fi

    TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    case "$new" in
      closed)
        hist_note="$note"
        [ -n "$skip_vet_reason" ] && hist_note="vet skipped: $skip_vet_reason"
        jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$hist_note" \
          '.status = $s
           | .closed = $ts
           | .closed_by = $actor
           | .history += [{ ts: $ts, actor: $actor, action: "closed", note: $note }]' \
          "$dir/bug.json" > "$dir/bug.json.tmp"
        ;;
      reopened)
        jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$note" \
          '.status = $s
           | .closed = null
           | .closed_by = null
           | .history += [{ ts: $ts, actor: $actor, action: "reopened", note: $note }]' \
          "$dir/bug.json" > "$dir/bug.json.tmp"
        ;;
      open)
        # Only reachable as initial state, blocked by transition rules above.
        echo "ERROR: cannot transition to 'open' (use 'reopened')" >&2
        exit 1
        ;;
    esac
    mv "$dir/bug.json.tmp" "$dir/bug.json"
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
