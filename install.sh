#!/usr/bin/env bash
# install.sh — copy rabbit-workflow into a target workspace.
#
# Usage:
#   install.sh [TARGET] [--all]
#
#   TARGET   directory to install into (default: $PWD)
#   --all    also copy archive material (archive/, .claude/docs/specs/,
#            .claude/docs/plans/, test/) — useful for fans / contributors
#            who want a closer look at how rabbit is built. Default is
#            minimal: just .claude/ + CLAUDE.md.
#
# The runtime work model is identical regardless of --all. The flag only
# affects which files come along for inspection; rabbit's behavior in the
# installed workspace is unchanged.

set -euo pipefail

TARGET=""
ALL=0
for arg in "$@"; do
  case "$arg" in
    --all) ALL=1 ;;
    -h|--help)
      sed -n '2,12p' "$0" >&2
      exit 0
      ;;
    -*)
      echo "Error: unknown option '$arg'" >&2
      exit 2
      ;;
    *)
      if [ -n "$TARGET" ]; then
        echo "Error: multiple TARGET values given" >&2
        exit 2
      fi
      TARGET="$arg"
      ;;
  esac
done
TARGET="${TARGET:-$PWD}"

if [[ -d "$TARGET/.claude" ]]; then
    echo "Error: $TARGET/.claude already exists." >&2
    echo "If developing rabbit-workflow, no install needed — open this directory in Claude Code." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.claude" ]]; then
    SRC="$SCRIPT_DIR"
else
    TMP="$(mktemp -d)"
    trap "rm -rf '$TMP'" EXIT INT TERM
    curl -fsSL https://github.com/USER/rabbit-workflow/archive/refs/heads/main.tar.gz \
        | tar -xz -C "$TMP" --strip-components=1
    SRC="$TMP"
fi

cp -r "$SRC/.claude" "$TARGET/.claude"
cp "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md"

# Always strip runtime-only and OS-level artifacts.
rm -f "$TARGET/.claude/settings.local.json"
rm -f "$TARGET/.claude/".nfs*
chmod +x "$TARGET/.claude/hooks/"*.sh 2>/dev/null || true

if [[ $ALL -eq 1 ]]; then
    # Bring extra inspection material along.
    [[ -d "$SRC/archive" ]] && cp -r "$SRC/archive" "$TARGET/archive"
    [[ -d "$SRC/test" ]]    && cp -r "$SRC/test"    "$TARGET/test"
    echo "rabbit-workflow installed to $TARGET (with --all: archive/ + test/ included; .claude/docs/ kept)"
else
    # Default install: strip dev-only docs the user doesn't need.
    rm -f "$TARGET/.claude/docs/specs/"*.md "$TARGET/.claude/docs/plans/"*.md
    echo "rabbit-workflow installed to $TARGET (minimal: .claude/ + CLAUDE.md only)"
fi
