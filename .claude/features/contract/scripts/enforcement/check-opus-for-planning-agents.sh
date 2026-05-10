#!/bin/bash
# check-opus-for-planning-agents.sh — enforce: any subagent whose description
# implies brainstorming, spec-writing, planning, design, or architecture work
# MUST declare model: opus in its frontmatter.
#
# Scans $AGENTS_DIR (default: .claude/agents/), reads YAML frontmatter, and
# emits a violation per non-conformant agent.
#
# Exit: 0 all conformant (or no agents); 1 one or more violations.

set -u

AGENTS_DIR="${AGENTS_DIR:-.claude/agents}"
[ ! -d "$AGENTS_DIR" ] && { echo "OK: no agents dir at $AGENTS_DIR (vacuous pass)"; exit 0; }

# Anything with these words in description triggers the rule.
PATTERN='brainstorm|spec|plan|design|architect'

violations=0
shopt -s nullglob
for f in "$AGENTS_DIR"/*.md; do
  front="$(awk '/^---$/{c++; next} c==1{print} c==2{exit}' "$f")"
  name=$(echo "$front" | sed -n 's/^name: *//p' | head -1)
  desc=$(echo "$front" | sed -n 's/^description: *//p' | head -1)
  model=$(echo "$front" | sed -n 's/^model: *//p' | head -1)

  if echo "$desc" | grep -qiE "$PATTERN"; then
    if [ "$model" != "opus" ]; then
      echo "VIOLATION: agent '$name' (file: $f) — description triggers planning rule but model='${model:-<unset>}' (must be 'opus')." >&2
      violations=$((violations+1))
    fi
  fi
done

if [ "$violations" -gt 0 ]; then
  echo "FAIL: $violations agent(s) violate Opus-for-planning rule." >&2
  exit 1
fi

echo "OK: all planning-class agents declare model: opus"
exit 0
