#!/bin/bash
# test-workspace-map.sh — verify rabbit-workspace-map skill invariants (spec invariants 6, 7, 8).
#
# Checks:
#   (a) workspace-map.sh exists and is executable
#   (b) workspace-map.json.schema.json exists and is valid JSON
#   (c) workspace-map.json.schema.json declares schemaVersion and required properties
#   (d) workspace-map.sh produces valid JSON without flags
#   (e) workspace-map.sh --human produces non-JSON human-readable output
#   (f) .claude/features/contract/skills/rabbit-workspace-map/SKILL.md exists (source of truth)
#   (g) feature.json surface.skills contains 'rabbit-workspace-map'
#   (h) SKILL.md references workspace-map.sh and the --human flag
#   (i) SKILL.md instructs Claude to directly execute workspace-map.sh on invocation
#       (imperative language; --human and JSON modes appear as actions, not just options)
#   (j) Deployed copy at .claude/skills/rabbit-workspace-map/SKILL.md is in sync with source

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git -C "$FEATURE_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")"
SCRIPT="$FEATURE_DIR/scripts/workspace-map.sh"
SCHEMA="$FEATURE_DIR/schemas/workspace-map.json.schema.json"
SKILL_MD="$FEATURE_DIR/skills/rabbit-workspace-map/SKILL.md"
FEATURE_JSON="$FEATURE_DIR/feature.json"
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

# (f) Source SKILL.md exists under contract feature
if [ ! -f "$SKILL_MD" ]; then
  echo "FAIL (f): source SKILL.md missing: $SKILL_MD" >&2
  FAIL=1
else
  echo "ok (f): rabbit-workspace-map/SKILL.md exists at source location"
fi

# (g) feature.json surface.skills contains 'rabbit-workspace-map'
if [ ! -f "$FEATURE_JSON" ]; then
  echo "FAIL (g): feature.json missing: $FEATURE_JSON" >&2
  FAIL=1
else
  HAS_SKILL=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
skills = d.get('surface', {}).get('skills', [])
print('yes' if 'rabbit-workspace-map' in skills else 'no')
" "$FEATURE_JSON" 2>/dev/null)
  if [ "$HAS_SKILL" != "yes" ]; then
    echo "FAIL (g): feature.json surface.skills does not contain 'rabbit-workspace-map'" >&2
    FAIL=1
  else
    echo "ok (g): feature.json declares rabbit-workspace-map skill"
  fi
fi

# (h) SKILL.md references workspace-map.sh and the --human flag
if [ -f "$SKILL_MD" ]; then
  if ! grep -q "workspace-map.sh" "$SKILL_MD"; then
    echo "FAIL (h): SKILL.md does not reference workspace-map.sh" >&2
    FAIL=1
  else
    echo "ok (h1): SKILL.md references workspace-map.sh"
  fi
  if ! grep -q -- "--human" "$SKILL_MD"; then
    echo "FAIL (h): SKILL.md does not reference --human flag" >&2
    FAIL=1
  else
    echo "ok (h2): SKILL.md references --human flag"
  fi
fi

# (i) SKILL.md instructs Claude to execute workspace-map.sh on invocation
#     Requires imperative execution language AND both modes mentioned as actions.
if [ -f "$SKILL_MD" ]; then
  # Must have an imperative execution directive near the top (Execute / Run / Invoke as a directive,
  # not buried under "Optional flags" or "When to Use" tables).
  if ! grep -E -i -q '^[[:space:]]*(execute|run|invoke|immediately[[:space:]]+(execute|run|invoke))\b' "$SKILL_MD"; then
    echo "FAIL (i): SKILL.md lacks an imperative execution directive (e.g., 'Execute', 'Run', 'Invoke') as a top-level instruction" >&2
    FAIL=1
  else
    echo "ok (i1): SKILL.md uses imperative execution language"
  fi

  # Must mention --human as the action for the readable case.
  if ! grep -E -q -- '(use|pass|with|add)[[:space:]]+`?--human`?' "$SKILL_MD"; then
    echo "FAIL (i): SKILL.md does not present --human as an action to take" >&2
    FAIL=1
  else
    echo "ok (i2): SKILL.md presents --human as an action"
  fi

  # Must mention default JSON as the action for the programmatic case.
  if ! grep -E -i -q '(default[[:space:]]+json|json[[:space:]]+(mode|output|by[[:space:]]+default)|without[[:space:]]+`?--human`?|omit[[:space:]]+`?--human`?)' "$SKILL_MD"; then
    echo "FAIL (i): SKILL.md does not present default JSON as the programmatic mode" >&2
    FAIL=1
  else
    echo "ok (i3): SKILL.md presents default JSON as programmatic mode"
  fi
fi

# (j) Deployed copy at .claude/skills/rabbit-workspace-map/SKILL.md is in sync with source
DEPLOYED_SKILL_MD="$REPO_ROOT/.claude/skills/rabbit-workspace-map/SKILL.md"
if [ -z "$REPO_ROOT" ]; then
  echo "FAIL (j): cannot resolve repo root for deployed-copy check" >&2
  FAIL=1
elif [ ! -f "$DEPLOYED_SKILL_MD" ]; then
  echo "FAIL (j): deployed SKILL.md missing: $DEPLOYED_SKILL_MD" >&2
  FAIL=1
elif ! diff -q "$SKILL_MD" "$DEPLOYED_SKILL_MD" >/dev/null 2>&1; then
  echo "FAIL (j): deployed SKILL.md differs from source — run cp -rp to sync" >&2
  FAIL=1
else
  echo "ok (j): deployed SKILL.md matches source"
fi

if [ "$FAIL" -ne 0 ]; then
  echo "test-workspace-map: FAIL" >&2
  exit 1
fi

echo "test-workspace-map: all checks passed."
