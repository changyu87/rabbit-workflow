#!/usr/bin/env bash
# workspace-map.sh — contract-driven workspace hierarchy map.
#
# Usage (show mode, default):
#   workspace-map.sh [--human] [--repo-root <path>]
#   Produces JSON conforming to workspace-map.json.schema.json v2.0.0.
#
# Usage (audit mode):
#   workspace-map.sh --audit [--human] [--repo-root <path>]
#   Produces findings-only JSON (deviations from contract).
#
# Usage (backlog path, legacy subcommand — preserved for rabbit-backlog):
#   workspace-map.sh backlog <feature-name> [--repo-root <path>]
#   Outputs the canonical backlog directory path for the named feature.
#
# Exit:
#   0  success
#   1  error
#
# Owner: rabbit-workflow team (contract feature)
# Version: 2.1.0
# Deprecation criterion: when rabbit features adopt a native workspace registry.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_root() {
  local root_arg="$1"
  if [ -n "$root_arg" ]; then
    echo "$root_arg"
  elif [ -n "${RABBIT_ROOT:-}" ]; then
    echo "$RABBIT_ROOT"
  else
    git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null \
      || { echo "ERROR: cannot resolve repo root" >&2; exit 1; }
  fi
}

# ---------------------------------------------------------------------------
# Legacy subcommand: backlog (used by rabbit-backlog/file-backlog-item.sh)
# ---------------------------------------------------------------------------
if [ "${1:-}" = "backlog" ]; then
  shift
  FEATURE_NAME="${1:-}"
  shift || true
  REPO_ROOT_ARG=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) REPO_ROOT_ARG="$2"; shift 2 ;;
      *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
    esac
  done
  if [ -z "$FEATURE_NAME" ]; then
    echo "ERROR: feature-name is required" >&2
    exit 1
  fi
  RESOLVED_ROOT="$(resolve_root "$REPO_ROOT_ARG")"
  echo "${RESOLVED_ROOT}/.claude/backlogs/${FEATURE_NAME}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
HUMAN=0
AUDIT=0
REPO_ROOT_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --human)     HUMAN=1; shift ;;
    --audit)     AUDIT=1; shift ;;
    --repo-root) REPO_ROOT_ARG="$2"; shift 2 ;;
    -h|--help)   echo "usage: workspace-map.sh [--human] [--audit] [--repo-root <path>]"; exit 0 ;;
    *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
  esac
done

REPO_ROOT="$(resolve_root "$REPO_ROOT_ARG")"

python3 "$SCRIPT_DIR/workspace-map.py" "$REPO_ROOT" "$HUMAN" "$AUDIT"
