#!/bin/bash
# check-naming.sh — enforce: every slash command, skill, and subagent under
# <root>/.claude/ MUST have a name beginning with 'rabbit-'.
#
# What is checked:
#   <root>/.claude/commands/*.md  (slash commands; basename without .md)
#   <root>/.claude/agents/*.md    (subagents;     basename without .md)
#   <root>/.claude/skills/*/      (skills;        directory name)
#
# Ignored (not artifact names):
#   README.md, CHANGELOG.md, *.txt, *.json
#
# Usage:  check-naming.sh [root]
#         (default root: current working directory)
#
# Exit:
#   0 all artifacts conformant (or no .claude tree)
#   1 one or more violations (each named on stderr)

set -u

root="${1:-.}"
[ ! -d "$root" ] && { echo "ERROR: not a directory: $root" >&2; exit 2; }

CLAUDE="$root/.claude"
[ ! -d "$CLAUDE" ] && { echo "OK: no .claude tree at $root (vacuous)"; exit 0; }

violations=0
flagged_paths=" "  # space-padded list of already-flagged paths for dedupe
flag() {
  local label="$1" name="$2" path="$3" reason="$4"
  case "$flagged_paths" in
    *" $path "*) return ;;  # already counted
  esac
  flagged_paths="$flagged_paths$path "
  echo "VIOLATION: $label $path — $reason ('$name')" >&2
  violations=$((violations+1))
}

# Slash commands: .claude/commands/*.md (excluding README.md, CHANGELOG.md)
if [ -d "$CLAUDE/commands" ]; then
  for f in "$CLAUDE/commands"/*.md; do
    [ -e "$f" ] || continue
    base="$(basename "$f" .md)"
    case "$base" in
      README|CHANGELOG) continue ;;
    esac
    case "$base" in
      rabbit-*) ;;
      *) flag "command" "$base" "$f" "must start with 'rabbit-'" ;;
    esac
  done
fi

# Subagents: .claude/agents/*.md (excluding README.md, CHANGELOG.md)
if [ -d "$CLAUDE/agents" ]; then
  for f in "$CLAUDE/agents"/*.md; do
    [ -e "$f" ] || continue
    base="$(basename "$f" .md)"
    case "$base" in
      README|CHANGELOG) continue ;;
    esac
    case "$base" in
      rabbit-*) ;;
      *) flag "agent" "$base" "$f" "must start with 'rabbit-'" ;;
    esac
  done
fi

# Skills: .claude/skills/*/ (each subdirectory is a skill)
if [ -d "$CLAUDE/skills" ]; then
  for d in "$CLAUDE/skills"/*/; do
    [ -d "$d" ] || continue
    base="$(basename "$d")"
    case "$base" in
      rabbit-*) ;;
      *) flag "skill" "$base" "$d" "must start with 'rabbit-'" ;;
    esac
  done
fi

# Second check: no file under .claude/ (excluding .claude/docs/) should have
# 'rwf-' as a basename prefix. Internal artifacts use 'rbt-'; user-facing use
# 'rabbit-'. The legacy 'rwf-' prefix is banned everywhere except historical
# docs (specs/plans that record what was true at the time).
while IFS= read -r f; do
  base="$(basename "$f")"
  case "$base" in
    rwf-*)
      flag "file" "$base" "$f" "legacy 'rwf-' prefix banned (use 'rbt-' for internal, 'rabbit-' for user-facing)"
      ;;
  esac
done < <(find "$CLAUDE" -mindepth 1 -path "$CLAUDE/docs" -prune -o -type f -print)

if [ "$violations" -gt 0 ]; then
  echo "FAIL: $violations naming violation(s) under $CLAUDE" >&2
  exit 1
fi
echo "OK: all artifacts under $CLAUDE start with 'rabbit-'; no 'rwf-' prefixes outside docs/"
exit 0
