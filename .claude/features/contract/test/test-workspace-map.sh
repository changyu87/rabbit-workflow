#!/bin/bash
# test-workspace-map.sh — verify rabbit-workspace-map skill invariants (spec invariants 6, 7, 8).
#
# Checks:
#   (a) workspace-map.sh exists and is executable
#   (b) workspace-map.json.schema.json exists and is valid JSON
#   (c) workspace-map.json.schema.json declares schemaVersion and required properties
#   (d) workspace-map.sh produces valid JSON without flags
#   (e) workspace-map.sh --human produces non-JSON human-readable output
#   (f) .claude/skills/rabbit-workspace-map/SKILL.md exists

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git -C "$FEATURE_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")"
SCRIPT="$FEATURE_DIR/scripts/workspace-map.sh"
SCHEMA="$FEATURE_DIR/schemas/workspace-map.json.schema.json"
SKILL_MD="$REPO_ROOT/.claude/skills/rabbit-workspace-map/SKILL.md"
FAIL=0

# (a) workspace-map.sh exists and is executable
if [ ! -f "$SCRIPT" ]; then
  echo "FAIL (a): workspace-map.sh missing: $SCRIPT" >&2
  FAIL=1
elif [ ! -x "$SCRIPT" ]; then
  echo "FAIL (a): workspace-map.sh not executable: $SCRIPT" >&2
  FAIL=1
else
  echo "ok (a): workspace-map.sh exists and is executable"
fi

# (b) workspace-map.json.schema.json exists and is valid JSON
if [ ! -f "$SCHEMA" ]; then
  echo "FAIL (b): workspace-map.json.schema.json missing: $SCHEMA" >&2
  FAIL=1
else
  if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$SCHEMA" 2>/dev/null; then
    echo "FAIL (b): workspace-map.json.schema.json is not valid JSON" >&2
    FAIL=1
  else
    echo "ok (b): workspace-map.json.schema.json exists and is valid JSON"
  fi
fi

# (c) schema declares schemaVersion and required property keys
if [ -f "$SCHEMA" ]; then
  SCHEMA_VERSION=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get('properties', {}).get('schemaVersion', {}).get('type', ''))
" "$SCHEMA" 2>/dev/null)
  if [ -z "$SCHEMA_VERSION" ]; then
    echo "FAIL (c): workspace-map.json.schema.json missing properties.schemaVersion" >&2
    FAIL=1
  else
    echo "ok (c): workspace-map.json.schema.json declares schemaVersion"
  fi

  REQUIRED_KEYS="features scripts schemas commands skills hooks"
  for key in $REQUIRED_KEYS; do
    HAS_KEY=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
props = d.get('properties', {})
print('yes' if '$key' in props else 'no')
" "$SCHEMA" 2>/dev/null)
    if [ "$HAS_KEY" != "yes" ]; then
      echo "FAIL (c): workspace-map.json.schema.json missing property: $key" >&2
      FAIL=1
    else
      echo "ok (c): schema has property: $key"
    fi
  done
fi

# (d) workspace-map.sh produces valid JSON without flags
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  JSON_OUT=$(bash "$SCRIPT" 2>/dev/null || true)
  if [ -z "$JSON_OUT" ]; then
    echo "FAIL (d): workspace-map.sh produced no output" >&2
    FAIL=1
  elif ! echo "$JSON_OUT" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "FAIL (d): workspace-map.sh output is not valid JSON" >&2
    FAIL=1
  else
    echo "ok (d): workspace-map.sh produces valid JSON"
  fi
fi

# (e) workspace-map.sh --human produces non-JSON human-readable output
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  HUMAN_OUT=$(bash "$SCRIPT" --human 2>/dev/null || true)
  if [ -z "$HUMAN_OUT" ]; then
    echo "FAIL (e): workspace-map.sh --human produced no output" >&2
    FAIL=1
  elif echo "$HUMAN_OUT" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "FAIL (e): workspace-map.sh --human output is JSON (expected human-readable text)" >&2
    FAIL=1
  else
    echo "ok (e): workspace-map.sh --human produces non-JSON output"
  fi
fi

# (f) SKILL.md exists
if [ -z "$REPO_ROOT" ]; then
  echo "FAIL (f): cannot resolve repo root" >&2
  FAIL=1
elif [ ! -f "$SKILL_MD" ]; then
  echo "FAIL (f): SKILL.md missing: $SKILL_MD" >&2
  FAIL=1
else
  echo "ok (f): rabbit-workspace-map/SKILL.md exists"
fi

if [ "$FAIL" -ne 0 ]; then
  echo "test-workspace-map: FAIL" >&2
  exit 1
fi

echo "test-workspace-map: all checks passed."
