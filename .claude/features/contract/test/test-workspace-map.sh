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

# (c) output schema schemaVersion is 2.0.0 (top-level field)
if [ -f "$SCHEMA" ]; then
  SCHEMA_VERSION=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get('schemaVersion', ''))
" "$SCHEMA" 2>/dev/null)
  if [ "$SCHEMA_VERSION" = "2.0.0" ]; then
    echo "ok (c): workspace-map.json.schema.json schemaVersion is 2.0.0"
  else
    echo "FAIL (c): workspace-map.json.schema.json schemaVersion is '$SCHEMA_VERSION' (expected 2.0.0)" >&2
    FAIL=1
  fi
fi

# (d) workspace-map.sh produces valid JSON with v2 shape (schemaVersion 2.0.0, roots array)
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  JSON_OUT=$(bash "$SCRIPT" 2>/dev/null || true)
  if [ -z "$JSON_OUT" ]; then
    echo "FAIL (d): workspace-map.sh produced no output" >&2
    FAIL=1
  elif ! echo "$JSON_OUT" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "FAIL (d): workspace-map.sh output is not valid JSON" >&2
    FAIL=1
  else
    echo "ok (d1): workspace-map.sh produces valid JSON"
    D_VER=$(echo "$JSON_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('schemaVersion',''))" 2>/dev/null)
    if [ "$D_VER" = "2.0.0" ]; then
      echo "ok (d2): output schemaVersion is 2.0.0"
    else
      echo "FAIL (d2): output schemaVersion is '$D_VER' (expected 2.0.0)" >&2
      FAIL=1
    fi
    HAS_ROOTS=$(echo "$JSON_OUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if 'roots' in d else 'no')" 2>/dev/null)
    if [ "$HAS_ROOTS" = "yes" ]; then
      echo "ok (d3): output has 'roots' key"
    else
      echo "FAIL (d3): output missing 'roots' key" >&2
      FAIL=1
    fi
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

# (g) feature.json surface.skills is [] (surface.skills retired — skill now declared in build-contract.json)
if [ ! -f "$FEATURE_JSON" ]; then
  echo "FAIL (g): feature.json missing: $FEATURE_JSON" >&2
  FAIL=1
else
  SKILLS=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(json.dumps(d.get('surface', {}).get('skills', [])))
" "$FEATURE_JSON" 2>/dev/null)
  if [ "$SKILLS" != "[]" ]; then
    echo "FAIL (g): feature.json surface.skills is not [] (was: $SKILLS)" >&2
    FAIL=1
  else
    echo "ok (g): feature.json surface.skills is [] (retired)"
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
  if ! grep -q -- "--audit" "$SKILL_MD"; then
    echo "FAIL (h3): SKILL.md does not reference --audit flag" >&2
    FAIL=1
  else
    echo "ok (h3): SKILL.md references --audit flag"
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

# (k) workspace-structure.json schema exists and is valid JSON
WS_SCHEMA="$FEATURE_DIR/schemas/workspace-structure.json"
if [ ! -f "$WS_SCHEMA" ]; then
  echo "FAIL (k): workspace-structure.json schema missing: $WS_SCHEMA" >&2
  FAIL=1
elif ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$WS_SCHEMA" 2>/dev/null; then
  echo "FAIL (k): workspace-structure.json schema is not valid JSON" >&2
  FAIL=1
else
  echo "ok (k): workspace-structure.json schema exists and is valid JSON"
fi

# (l) workspace-structure.json schema has required top-level properties
if [ -f "$WS_SCHEMA" ]; then
  for field in schema_version owner root nodes; do
    HAS=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
props = d.get('properties', {})
print('yes' if '$field' in props else 'no')
" "$WS_SCHEMA" 2>/dev/null)
    if [ "$HAS" != "yes" ]; then
      echo "FAIL (l): workspace-structure.json schema missing property: $field" >&2
      FAIL=1
    else
      echo "ok (l): schema has property: $field"
    fi
  done
fi

# (m) .claude/workspace-structure.json exists and is valid JSON
RABBIT_DECL="$REPO_ROOT/.claude/workspace-structure.json"
if [ ! -f "$RABBIT_DECL" ]; then
  echo "FAIL (m): .claude/workspace-structure.json missing: $RABBIT_DECL" >&2
  FAIL=1
elif ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$RABBIT_DECL" 2>/dev/null; then
  echo "FAIL (m): .claude/workspace-structure.json is not valid JSON" >&2
  FAIL=1
else
  echo "ok (m): .claude/workspace-structure.json exists and is valid JSON"
fi

# (n) rabbit declaration has root "rabbit" and required top-level nodes
if [ -f "$RABBIT_DECL" ]; then
  RABBIT_ROOT_TAG=$(python3 -c "import json; d=json.load(open('$RABBIT_DECL')); print(d.get('root',''))" 2>/dev/null)
  if [ "$RABBIT_ROOT_TAG" != "rabbit" ]; then
    echo "FAIL (n): .claude/workspace-structure.json root is not 'rabbit' (got: $RABBIT_ROOT_TAG)" >&2
    FAIL=1
  else
    echo "ok (n): declaration root is 'rabbit'"
  fi

  for req_node in features skills hooks commands; do
    HAS_NODE=$(python3 -c "
import json
d = json.load(open('$RABBIT_DECL'))
names = [n['name'] for n in d.get('nodes', [])]
print('yes' if '$req_node' in names else 'no')
" 2>/dev/null)
    if [ "$HAS_NODE" != "yes" ]; then
      echo "FAIL (n): rabbit declaration missing required node: $req_node" >&2
      FAIL=1
    else
      echo "ok (n): rabbit declaration declares node: $req_node"
    fi
  done
fi

# (o) output schema declares schemaVersion 2.0.0 at top level
if [ -f "$SCHEMA" ]; then
  O_VER=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get('schemaVersion', ''))
" "$SCHEMA" 2>/dev/null)
  if [ "$O_VER" = "2.0.0" ]; then
    echo "ok (o): output schema schemaVersion is 2.0.0"
  else
    echo "FAIL (o): output schema schemaVersion is '$O_VER' (expected 2.0.0)" >&2
    FAIL=1
  fi
fi

# (p) output schema has 'roots' property (show mode) and not stale 'features' flat array
if [ -f "$SCHEMA" ]; then
  HAS_ROOTS=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
def has_roots(obj):
    if 'roots' in obj.get('properties', {}):
        return True
    for branch in obj.get('oneOf', []):
        if 'roots' in branch.get('properties', {}):
            return True
    return False
print('yes' if has_roots(d) else 'no')
" "$SCHEMA" 2>/dev/null)
  if [ "$HAS_ROOTS" = "yes" ]; then
    echo "ok (p1): output schema has 'roots' property"
  else
    echo "FAIL (p1): output schema missing 'roots' property" >&2
    FAIL=1
  fi

  HAS_OLD_FEATURES=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print('yes' if 'features' in d.get('properties', {}) else 'no')
" "$SCHEMA" 2>/dev/null)
  if [ "$HAS_OLD_FEATURES" = "no" ]; then
    echo "ok (p2): output schema does not have stale 'features' flat array"
  else
    echo "FAIL (p2): output schema still has old 'features' flat array (must be removed in v2)" >&2
    FAIL=1
  fi
fi

# (q) output schema has 'findings' property (audit mode)
if [ -f "$SCHEMA" ]; then
  HAS_FINDINGS=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
def has_findings(obj):
    if 'findings' in obj.get('properties', {}):
        return True
    for branch in obj.get('oneOf', []):
        if 'findings' in branch.get('properties', {}):
            return True
    return False
print('yes' if has_findings(d) else 'no')
" "$SCHEMA" 2>/dev/null)
  if [ "$HAS_FINDINGS" = "yes" ]; then
    echo "ok (q): output schema has 'findings' property (audit mode)"
  else
    echo "FAIL (q): output schema missing 'findings' property" >&2
    FAIL=1
  fi
fi

# Behavioral tests using --repo-root with a controlled temp directory.
BT_TMP=$(mktemp -d)
trap 'rm -rf "$BT_TMP"' EXIT

git -C "$BT_TMP" init --quiet
git -C "$BT_TMP" config user.email "test@rabbit"
git -C "$BT_TMP" config user.name "t"
git -C "$BT_TMP" commit --allow-empty -m "init" --quiet

mkdir -p "$BT_TMP/.claude/declared_req" "$BT_TMP/.claude/extra_unknown"
# declared_opt intentionally NOT created; declared_req_missing intentionally NOT created

cat > "$BT_TMP/.claude/workspace-structure.json" <<'DECL'
{
  "schema_version": "1.0.0",
  "owner": "test",
  "root": "rabbit",
  "nodes": [
    { "name": "declared_req",         "required": true,  "description": "required dir, present", "children": [] },
    { "name": "declared_opt",         "required": false, "description": "optional dir, absent",  "children": [] },
    { "name": "declared_req_missing", "required": true,  "description": "required dir, absent",  "children": [] }
  ]
}
DECL

# (r) show mode JSON: schemaVersion 2.0.0, declared_req present, declared_opt missing, extra_unknown annotated
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  BT_OUT=$(bash "$SCRIPT" --repo-root "$BT_TMP" 2>/dev/null)
  BT_VER=$(echo "$BT_OUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('schemaVersion',''))" 2>/dev/null)
  if [ "$BT_VER" = "2.0.0" ]; then
    echo "ok (r1): show mode schemaVersion is 2.0.0"
  else
    echo "FAIL (r1): show mode schemaVersion is '$BT_VER' (expected 2.0.0)" >&2
    FAIL=1
  fi

  BT_REQ=$(echo "$BT_OUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
nodes = d['roots'][0]['nodes']
n = next((x for x in nodes if x['name'] == 'declared_req'), None)
print(n['status'] if n else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_REQ" = "present" ]; then
    echo "ok (r2): declared_req status is 'present'"
  else
    echo "FAIL (r2): declared_req status is '$BT_REQ' (expected 'present')" >&2
    FAIL=1
  fi

  BT_OPT=$(echo "$BT_OUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
nodes = d['roots'][0]['nodes']
n = next((x for x in nodes if x['name'] == 'declared_opt'), None)
print(n['status'] if n else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_OPT" = "missing" ]; then
    echo "ok (r3): declared_opt status is 'missing'"
  else
    echo "FAIL (r3): declared_opt status is '$BT_OPT' (expected 'missing')" >&2
    FAIL=1
  fi

  BT_UNK=$(echo "$BT_OUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
nodes = d['roots'][0]['nodes']
n = next((x for x in nodes if x['name'] == 'extra_unknown'), None)
print('{},{}'.format(n['status'] if n else 'NOT_FOUND', str(n['required']) if n else 'X'))
" 2>/dev/null)
  if [ "$BT_UNK" = "unknown,None" ]; then
    echo "ok (r4): extra_unknown status is 'unknown' with required null"
  else
    echo "FAIL (r4): extra_unknown is '$BT_UNK' (expected 'unknown,None')" >&2
    FAIL=1
  fi
fi

# (s) audit mode: missing required→error, unknown→warn, missing optional→NO finding
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  BT_AUDIT=$(bash "$SCRIPT" --repo-root "$BT_TMP" --audit 2>/dev/null)

  HAS_FINDINGS=$(echo "$BT_AUDIT" | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if 'findings' in d else 'no')" 2>/dev/null)
  if [ "$HAS_FINDINGS" = "yes" ]; then
    echo "ok (s1): audit output has findings array"
  else
    echo "FAIL (s1): audit output missing findings array" >&2
    FAIL=1
  fi

  BT_S2=$(echo "$BT_AUDIT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
f = next((x for x in d['findings'] if x['type'] == 'missing_required' and 'declared_req_missing' in x['path']), None)
print(f['severity'] if f else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_S2" = "error" ]; then
    echo "ok (s2): missing required node emits severity 'error'"
  else
    echo "FAIL (s2): missing_required finding not found or wrong severity (got: '$BT_S2')" >&2
    FAIL=1
  fi

  BT_S3=$(echo "$BT_AUDIT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
f = next((x for x in d['findings'] if x['type'] == 'unknown' and 'extra_unknown' in x['path']), None)
print(f['severity'] if f else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_S3" = "warn" ]; then
    echo "ok (s3): unknown node emits severity 'warn'"
  else
    echo "FAIL (s3): unknown finding not found or wrong severity (got: '$BT_S3')" >&2
    FAIL=1
  fi

  BT_S4=$(echo "$BT_AUDIT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
f = next((x for x in d['findings'] if 'declared_opt' in x['path']), None)
print('found' if f else 'not_found')
" 2>/dev/null)
  if [ "$BT_S4" = "not_found" ]; then
    echo "ok (s4): missing optional node emits no audit finding"
  else
    echo "FAIL (s4): missing optional node unexpectedly emitted a finding" >&2
    FAIL=1
  fi
fi

# (t) user project without declaration → declaration "missing"
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  mkdir -p "$BT_TMP/my-project"
  BT_OUT2=$(bash "$SCRIPT" --repo-root "$BT_TMP" 2>/dev/null)
  BT_PROJ_DECL=$(echo "$BT_OUT2" | python3 -c "
import json, sys
d = json.load(sys.stdin)
proj = next((r for r in d['roots'] if r['root'] == 'my-project'), None)
print(proj['declaration'] if proj else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_PROJ_DECL" = "missing" ]; then
    echo "ok (t): user project without declaration has declaration 'missing'"
  else
    echo "FAIL (t): user project declaration status is '$BT_PROJ_DECL' (expected 'missing')" >&2
    FAIL=1
  fi
fi

# (u) audit emits missing_declaration warn for user project without workspace-structure.json
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  BT_AUDIT2=$(bash "$SCRIPT" --repo-root "$BT_TMP" --audit 2>/dev/null)
  BT_U=$(echo "$BT_AUDIT2" | python3 -c "
import json, sys
d = json.load(sys.stdin)
f = next((x for x in d['findings'] if x['type'] == 'missing_declaration' and 'my-project' in x['path']), None)
print(f['severity'] if f else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_U" = "warn" ]; then
    echo "ok (u): missing user project declaration emits 'warn' finding"
  else
    echo "FAIL (u): missing_declaration finding not found or wrong severity (got: '$BT_U')" >&2
    FAIL=1
  fi
fi

# (v) workspace-map.sh --audit produces valid JSON with findings key
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  AUDIT_OUT=$(bash "$SCRIPT" --audit 2>/dev/null || true)
  if [ -z "$AUDIT_OUT" ]; then
    echo "FAIL (v): workspace-map.sh --audit produced no output" >&2
    FAIL=1
  elif ! echo "$AUDIT_OUT" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "FAIL (v): workspace-map.sh --audit output is not valid JSON" >&2
    FAIL=1
  else
    echo "ok (v1): workspace-map.sh --audit produces valid JSON"
    V_FIND=$(echo "$AUDIT_OUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if 'findings' in d else 'no')" 2>/dev/null)
    if [ "$V_FIND" = "yes" ]; then
      echo "ok (v2): audit output has 'findings' key"
    else
      echo "FAIL (v2): audit output missing 'findings' key" >&2
      FAIL=1
    fi
  fi
fi

# (w) workspace-map.sh --audit --human produces non-JSON human-readable output
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  AUDIT_H_OUT=$(bash "$SCRIPT" --audit --human 2>/dev/null || true)
  if [ -z "$AUDIT_H_OUT" ]; then
    echo "FAIL (w): workspace-map.sh --audit --human produced no output" >&2
    FAIL=1
  elif echo "$AUDIT_H_OUT" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "FAIL (w): workspace-map.sh --audit --human output is JSON (expected human-readable text)" >&2
    FAIL=1
  else
    echo "ok (w): workspace-map.sh --audit --human produces non-JSON output"
  fi
fi

if [ "$FAIL" -ne 0 ]; then
  echo "test-workspace-map: FAIL" >&2
  exit 1
fi

echo "test-workspace-map: all checks passed."
