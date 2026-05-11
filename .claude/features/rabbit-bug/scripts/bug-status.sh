#!/bin/bash
# bug-status.sh -- read or transition bug status.
# The description field is NEVER modified after initial filing.
# Exit: 0=ok 1=denied 2=inv-err

set -u

usage() {
  echo "usage: bug-status.sh get DIR" 1>&2
  echo "  set DIR STATUS --note R [--actor A] [--skip-vet-reason R] [--fix-commits C] [--touched-files F]" 1>&2
}

cmd="${1:-}"; shift || true

case "$cmd" in
  get)
    dir="${1:-}"; [ -z "$dir" ] && { usage; exit 2; }
    [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" 1>&2; exit 2; }
    [ -f "$dir/bug.json" ] || { echo "ERROR: missing $dir/bug.json" 1>&2; exit 2; }
    jq -r ".status" "$dir/bug.json"
    ;;
  set)
    dir="${1:-}"; new="${2:-}"; note=""; actor="${USER:-unknown}"
    skip_vet_reason=""; fix_commits=""; touched_files=""
    shift 2 2>/dev/null || true
    while [ $# -gt 0 ]; do
      case "$1" in
        --reason)          note="$2"; shift 2 ;;
        --actor)           actor="$2"; shift 2 ;;
        --skip-vet-reason) skip_vet_reason="$2"; shift 2 ;;
        --fix-commits)     fix_commits="$2"; shift 2 ;;
        --touched-files)   touched_files="$2"; shift 2 ;;
        *) echo "unknown arg: $1" 1>&2; exit 2 ;;
      esac
    done
    [ -z "$dir" ] || [ -z "$new" ] && { usage; exit 2; }
    [ -z "$note" ] && { echo "ERROR: --reason is required" 1>&2; exit 1; }
    [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" 1>&2; exit 2; }
    [ -f "$dir/bug.json" ] || { echo "ERROR: missing $dir/bug.json" 1>&2; exit 2; }

    case "$new" in
      open|closed|reopened|refused) ;;
      *) echo "ERROR: invalid status (allowed: open|closed|reopened|refused)" 1>&2; exit 1 ;;
    esac

    cur=$(jq -r ".status" "$dir/bug.json")

    [ "$cur" = "$new" ] && { echo "no-op: already $cur"; exit 0; }

    allowed=0
    case "${cur}->${new}" in
      "open->closed")     allowed=1 ;;
      "closed->reopened") allowed=1 ;;
      "reopened->closed") allowed=1 ;;
      "open->refused")    allowed=1 ;;
      "reopened->refused") allowed=1 ;;
      "refused->reopened") allowed=1 ;;
    esac
    [ "$allowed" -ne 1 ] && { echo "ERROR: transition not allowed" 1>&2; exit 1; }

    TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    if [ "$new" = "closed" ]; then
      if [ -n "$skip_vet_reason" ]; then
        note="[skip-vet: $skip_vet_reason] $note"
      elif [ ! -f "$dir/vet-triage.json" ] && [ ! -f "$dir/tdd-gap.json" ]; then
        echo "ERROR (R7): cannot close without vet artifact" 1>&2; exit 1
      fi
      if [ -z "$fix_commits" ] && [ -z "$skip_vet_reason" ]; then
        echo "ERROR: --fix-commits is required when closing a bug (use --skip-vet-reason to bypass)" 1>&2; exit 1
      fi
    fi

    if [ "$new" = "refused" ] && [ -n "$fix_commits" ]; then
      echo "ERROR: --fix-commits is not applicable for refused status" 1>&2; exit 1
    fi

    case "$new" in
      closed)
        jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$note" \
           --arg fc "$fix_commits" --arg tf "$touched_files" \
           '.status = $s | .closed = $ts | .closed_by = $actor |
            .history += [{ ts: $ts, actor: $actor, action: "closed", note: $note } +
              if $fc != "" and $tf != "" then { fix_commits: $fc, touched_files: $tf }
              elif $fc != "" then { fix_commits: $fc }
              elif $tf != "" then { touched_files: $tf }
              else {} end]' \
           "$dir/bug.json" > "$dir/bug.json.tmp"
        ;;
      reopened)
        jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$note" \
           --arg fc "$fix_commits" --arg tf "$touched_files" \
           '.status = $s | .closed = null | .closed_by = null |
            .history += [{ ts: $ts, actor: $actor, action: "reopened", note: $note } +
              if $fc != "" and $tf != "" then { fix_commits: $fc, touched_files: $tf }
              elif $fc != "" then { fix_commits: $fc }
              elif $tf != "" then { touched_files: $tf }
              else {} end]' \
           "$dir/bug.json" > "$dir/bug.json.tmp"
        ;;
      refused)
        jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$note" \
           --arg fc "$fix_commits" --arg tf "$touched_files" \
           '.status = $s | .closed = null | .closed_by = null |
            .history += [{ ts: $ts, actor: $actor, action: "refused", note: $note } +
              if $fc != "" and $tf != "" then { fix_commits: $fc, touched_files: $tf }
              elif $fc != "" then { fix_commits: $fc }
              elif $tf != "" then { touched_files: $tf }
              else {} end]' \
           "$dir/bug.json" > "$dir/bug.json.tmp"
        ;;
      open) echo "ERROR: cannot transition to open" 1>&2; exit 1 ;;
    esac
mv "$dir/bug.json.tmp" "$dir/bug.json"
    REPO_ROOT="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null || true)"
    if [ -n "$REPO_ROOT" ]; then
      _reason_short="$(echo "$note" | head -c 60)"
      git -C "$REPO_ROOT" add "$dir/bug.json" 2>/dev/null && \
      git -C "$REPO_ROOT" commit -m "bug: $cur -> $new ($_reason_short)" 2>/dev/null || true
    fi
    echo "transitioned"
    ;;
  ""|--help|help|-h) usage; [ -z "$cmd" ] && exit 2 || exit 0 ;;
  *) echo "ERROR: unknown subcommand: $cmd" 1>&2; usage; exit 2 ;;
esac
