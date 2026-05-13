# rabbit-workspace-map Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Rabbit workspace note:** All implementation touches go through the rabbit TDD state machine. The main session dispatches subagents via `dispatch-feature-tdd.sh` for the `contract` feature. The subagent executes these tasks within its TDD cycle (spec-update → test-red → impl → test-green).

**Goal:** Replace the ad-hoc filesystem-walk workspace map with a contract-driven hierarchy map that reads `workspace-structure.json` declarations and validates the actual workspace against them.

**Architecture:** A new JSON schema (`workspace-structure.json`) defines the shape of per-project structural declarations. Rabbit's own declaration lives at `.claude/workspace-structure.json`; user projects declare theirs at `<project-root>/workspace-structure.json`. The rewritten `workspace-map.sh` loads these declarations and emits either a hierarchy view (show mode) or deviation findings (audit mode).

**Tech Stack:** Bash + embedded Python 3 (consistent with existing script). No external dependencies.

---

## Feature Scope

All changes are within the **`contract`** feature:
- `.claude/features/contract/schemas/`
- `.claude/features/contract/scripts/workspace-map.sh`
- `.claude/features/contract/skills/rabbit-workspace-map/SKILL.md`
- `.claude/features/contract/test/test-workspace-map.sh`

Plus two non-feature files:
- `.claude/workspace-structure.json` (rabbit's own declaration — new file at `.claude/` root)
- `.claude/skills/rabbit-workspace-map/SKILL.md` (deployed copy — synced from source via `cp`)

---

## File Map

| Action | File |
|--------|------|
| **Create** | `.claude/features/contract/schemas/workspace-structure.json` |
| **Create** | `.claude/workspace-structure.json` |
| **Modify** | `.claude/features/contract/schemas/workspace-map.json.schema.json` |
| **Modify** | `.claude/features/contract/scripts/workspace-map.sh` |
| **Modify** | `.claude/features/contract/test/test-workspace-map.sh` |
| **Modify** | `.claude/features/contract/skills/rabbit-workspace-map/SKILL.md` |
| **Sync** | `.claude/skills/rabbit-workspace-map/SKILL.md` (copy from source after SKILL.md update) |

Consumer tests (`rabbit-bug`, `rabbit-backlog`, `rabbit-cage`) do **not** need changes — they test the `backlog` subcommand and PATH-shim behavior, neither of which changes.

---

## Task 1: Create the node-tree schema

**Files:**
- Create: `.claude/features/contract/schemas/workspace-structure.json`

- [ ] **Step 1: Write the failing test for schema existence**

Add to `.claude/features/contract/test/test-workspace-map.sh` (insert before final exit, keep existing checks intact):

```bash
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

# (l) workspace-structure.json schema has required top-level fields
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep -E "^(ok|FAIL) \([kl]\)"
```

Expected: `FAIL (k): workspace-structure.json schema missing`

- [ ] **Step 3: Create the schema file**

Write `.claude/features/contract/schemas/workspace-structure.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "schemaVersion": "1.0.0",
  "title": "workspace-structure",
  "description": "Schema for workspace-structure.json declaration files. Each project root carries one to declare its expected directory hierarchy.",
  "owner": "rabbit-workflow team (contract feature)",
  "deprecation_criterion": "when a native Claude Code workspace registry supersedes this schema",
  "type": "object",
  "required": ["schema_version", "owner", "root", "nodes"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
      "description": "Semver of the workspace-structure schema this declaration conforms to."
    },
    "owner": {
      "type": "string",
      "minLength": 1,
      "description": "Owner of this declaration."
    },
    "root": {
      "type": "string",
      "minLength": 1,
      "description": "Tag identifying this root (e.g. 'rabbit', 'my-project')."
    },
    "nodes": {
      "type": "array",
      "description": "Top-level declared directory nodes.",
      "items": { "$ref": "#/definitions/node" }
    }
  },
  "definitions": {
    "node": {
      "type": "object",
      "required": ["name", "required", "description", "children"],
      "additionalProperties": false,
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "required": { "type": "boolean" },
        "description": { "type": "string" },
        "children": {
          "type": "array",
          "items": { "$ref": "#/definitions/node" }
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep -E "^(ok|FAIL) \([kl]\)"
```

Expected: all `ok (k)` and `ok (l)` lines.

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/schemas/workspace-structure.json \
        .claude/features/contract/test/test-workspace-map.sh
git commit -m "feat(contract): add workspace-structure.json schema for contract-driven workspace map"
```

---

## Task 2: Create rabbit's own structural declaration

**Files:**
- Create: `.claude/workspace-structure.json`

- [ ] **Step 1: Write the failing test for rabbit's declaration**

Add to `.claude/features/contract/test/test-workspace-map.sh`:

```bash
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

# (n) rabbit declaration has root "rabbit" and required top-level nodes: features, skills, hooks, commands
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep -E "^(ok|FAIL) \([mn]\)"
```

Expected: `FAIL (m): .claude/workspace-structure.json missing`

- [ ] **Step 3: Create rabbit's declaration**

Write `.claude/workspace-structure.json`:

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "root": "rabbit",
  "nodes": [
    {
      "name": "features",
      "required": true,
      "description": "all feature source directories",
      "children": [
        { "name": "contract",        "required": true,  "description": "cross-feature schemas, dispatch scripts, enforcement", "children": [] },
        { "name": "policy",          "required": true,  "description": "canonical rule docs (philosophy, spec-rules, coding-rules, workflow-rules)", "children": [] },
        { "name": "rabbit-backlog",  "required": true,  "description": "backlog item filing and lifecycle", "children": [] },
        { "name": "rabbit-bug",      "required": true,  "description": "bug filing, tracking, and lifecycle", "children": [] },
        { "name": "rabbit-cage",     "required": true,  "description": "Claude Code surface owner", "children": [] },
        { "name": "tdd-state-machine","required": true, "description": "forward-only TDD state machine", "children": [] }
      ]
    },
    { "name": "skills",    "required": true,  "description": "skill library (copied from feature sources via build-contract.json)", "children": [] },
    { "name": "hooks",     "required": true,  "description": "hook scripts (copied from rabbit-cage via build-contract.json)", "children": [] },
    { "name": "commands",  "required": true,  "description": "slash commands (copied from feature sources via build-contract.json)", "children": [] },
    { "name": "bugs",      "required": false, "description": "centralized bug tracker (created on first bug filing)", "children": [] },
    { "name": "backlogs",  "required": false, "description": "centralized backlog tracker (created on first backlog filing)", "children": [] }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep -E "^(ok|FAIL) \([mn]\)"
```

Expected: all `ok (m)` and `ok (n)` lines.

- [ ] **Step 5: Commit**

```bash
git add .claude/workspace-structure.json \
        .claude/features/contract/test/test-workspace-map.sh
git commit -m "feat(contract): add rabbit workspace-structure.json declaration and tests"
```

---

## Task 3: Update output schema to v2.0.0

**Files:**
- Modify: `.claude/features/contract/schemas/workspace-map.json.schema.json`

- [ ] **Step 1: Update stale check (c) and write failing tests for v2 output shape**

Check (c) in the existing test reads `properties.schemaVersion` at the top level. After this task replaces the schema with a `oneOf` structure, that path no longer exists — check (c) must be updated here to avoid breaking Task 4's full test run.

Replace the existing `# (c)` block in `.claude/features/contract/test/test-workspace-map.sh` with:

```bash
# (c) output schema schemaVersion is 2.0.0 (top-level field, not inside properties)
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
```

Then add the new checks (o), (p), (q):

```bash
# (o) output schema schemaVersion field declares v2 format
if [ -f "$SCHEMA" ]; then
  SCHEMA_VER_VAL=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
# Check for v2 schemaVersion const/enum
sv = d.get('properties', {}).get('schemaVersion', {})
enum_val = sv.get('enum', sv.get('const', [None]))[0] if isinstance(sv.get('enum', sv.get('const', None)), list) else sv.get('const', '')
print(enum_val or '')
" "$SCHEMA" 2>/dev/null)
  if [ "$SCHEMA_VER_VAL" = "2.0.0" ]; then
    echo "ok (o): output schema declares schemaVersion 2.0.0"
  else
    echo "FAIL (o): output schema does not declare schemaVersion 2.0.0 (got: '$SCHEMA_VER_VAL')" >&2
    FAIL=1
  fi
fi

# (p) output schema has 'roots' property (not old flat arrays like 'features')
if [ -f "$SCHEMA" ]; then
  HAS_ROOTS=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
# oneOf: check either top-level properties or oneOf branches
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
    echo "ok (p): output schema has 'roots' property"
  else
    echo "FAIL (p): output schema missing 'roots' property (still v1 shape?)" >&2
    FAIL=1
  fi

  HAS_FEATURES=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print('yes' if 'features' in d.get('properties', {}) else 'no')
" "$SCHEMA" 2>/dev/null)
  if [ "$HAS_FEATURES" = "yes" ]; then
    echo "FAIL (p): output schema still has old 'features' flat array (must be removed in v2)" >&2
    FAIL=1
  else
    echo "ok (p): output schema does not have stale 'features' flat array"
  fi
fi

# (q) --audit output has 'findings' property in schema
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
    echo "FAIL (q): output schema missing 'findings' property (audit mode not declared)" >&2
    FAIL=1
  fi
fi
```

- [ ] **Step 2: Run test to verify it fails**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep -E "^(ok|FAIL) \([opq]\)"
```

Expected: `FAIL (o)`, `FAIL (p)` (roots missing), `FAIL (q)`.

- [ ] **Step 3: Rewrite the output schema**

Replace the full contents of `.claude/features/contract/schemas/workspace-map.json.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "schemaVersion": "2.0.0",
  "title": "workspace-map output",
  "description": "Versioned JSON schema for workspace-map.sh v2 output. Two shapes: show mode (roots array) and audit mode (findings array).",
  "owner": "rabbit-workflow team (contract feature)",
  "deprecation_criterion": "when a native Claude Code workspace registry supersedes this schema",
  "oneOf": [
    {
      "title": "show mode output",
      "type": "object",
      "required": ["schemaVersion", "repoRoot", "roots"],
      "additionalProperties": false,
      "properties": {
        "schemaVersion": { "type": "string", "const": "2.0.0" },
        "repoRoot": { "type": "string", "description": "Absolute path to the repository root." },
        "roots": {
          "type": "array",
          "description": "One entry per recognized project root (rabbit .claude/ root first, then user project roots).",
          "items": {
            "type": "object",
            "required": ["root", "path", "declaration", "nodes"],
            "additionalProperties": false,
            "properties": {
              "root": { "type": "string", "description": "Tag from the declaration file, or the dir name if no declaration found." },
              "path": { "type": "string", "description": "Relative path from repo root." },
              "declaration": { "type": "string", "enum": ["found", "missing"], "description": "Whether a workspace-structure.json was found at this root." },
              "nodes": {
                "type": "array",
                "items": { "$ref": "#/definitions/annotated_node" }
              }
            }
          }
        }
      }
    },
    {
      "title": "audit mode output",
      "type": "object",
      "required": ["schemaVersion", "findings"],
      "additionalProperties": false,
      "properties": {
        "schemaVersion": { "type": "string", "const": "2.0.0" },
        "findings": {
          "type": "array",
          "description": "Deviations from contract: missing required nodes and unknown filesystem entries.",
          "items": {
            "type": "object",
            "required": ["severity", "type", "path", "root"],
            "additionalProperties": false,
            "properties": {
              "severity": { "type": "string", "enum": ["error", "warn"] },
              "type": { "type": "string", "enum": ["missing_required", "unknown", "missing_declaration"] },
              "path": { "type": "string", "description": "Relative path from repo root of the finding." },
              "root": { "type": "string", "description": "Root tag this finding belongs to." }
            }
          }
        }
      }
    }
  ],
  "definitions": {
    "annotated_node": {
      "type": "object",
      "required": ["name", "status", "children"],
      "additionalProperties": false,
      "properties": {
        "name": { "type": "string" },
        "required": { "type": ["boolean", "null"], "description": "true/false from declaration; null means unknown (not in contract)." },
        "description": { "type": "string" },
        "status": { "type": "string", "enum": ["present", "missing", "unknown"] },
        "children": {
          "type": "array",
          "items": { "$ref": "#/definitions/annotated_node" }
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep -E "^(ok|FAIL) \([opq]\)"
```

Expected: all `ok (o)`, `ok (p)`, `ok (q)` lines.

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/schemas/workspace-map.json.schema.json \
        .claude/features/contract/test/test-workspace-map.sh
git commit -m "feat(contract): update workspace-map output schema to v2.0.0 (roots/findings)"
```

---

## Task 4: Rewrite `workspace-map.sh`

**Files:**
- Modify: `.claude/features/contract/scripts/workspace-map.sh`

- [ ] **Step 1: Write failing behavioral tests**

Add to `.claude/features/contract/test/test-workspace-map.sh` (these test actual behavior using `--repo-root` with a controlled temp dir):

```bash
# Behavioral tests: use --repo-root to point at a controlled temp directory.
# Setup: temp repo with .claude/workspace-structure.json declaring two nodes:
#   - declared_req/  (required: true)
#   - declared_opt/  (required: false)
# Filesystem state:
#   - .claude/declared_req/  EXISTS
#   - .claude/declared_opt/  MISSING
#   - .claude/extra_unknown/ EXISTS (not in declaration)

BT_TMP=$(mktemp -d)
trap 'rm -rf "$BT_TMP"' EXIT

git -C "$BT_TMP" init --quiet
git -C "$BT_TMP" config user.email "test@rabbit" && git -C "$BT_TMP" config user.name "t"
git -C "$BT_TMP" commit --allow-empty -m "init" --quiet

mkdir -p "$BT_TMP/.claude/declared_req" "$BT_TMP/.claude/extra_unknown"
# declared_opt intentionally NOT created

cat > "$BT_TMP/.claude/workspace-structure.json" <<'DECL'
{
  "schema_version": "1.0.0",
  "owner": "test",
  "root": "rabbit",
  "nodes": [
    { "name": "declared_req", "required": true,  "description": "required dir", "children": [] },
    { "name": "declared_opt", "required": false, "description": "optional dir", "children": [] }
  ]
}
DECL

# (r) show mode JSON: schemaVersion is "2.0.0" and roots array present
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  BT_OUT=$(bash "$SCRIPT" --repo-root "$BT_TMP" 2>/dev/null)
  BT_VER=$(echo "$BT_OUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('schemaVersion',''))" 2>/dev/null)
  if [ "$BT_VER" = "2.0.0" ]; then
    echo "ok (r1): show mode output schemaVersion is 2.0.0"
  else
    echo "FAIL (r1): show mode schemaVersion is '$BT_VER' (expected 2.0.0)" >&2
    FAIL=1
  fi

  # (r2) declared_req is present
  BT_REQ=$(echo "$BT_OUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
nodes = d['roots'][0]['nodes']
req = next((n for n in nodes if n['name'] == 'declared_req'), None)
print(req['status'] if req else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_REQ" = "present" ]; then
    echo "ok (r2): declared_req status is 'present'"
  else
    echo "FAIL (r2): declared_req status is '$BT_REQ' (expected 'present')" >&2
    FAIL=1
  fi

  # (r3) declared_opt is missing
  BT_OPT=$(echo "$BT_OUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
nodes = d['roots'][0]['nodes']
opt = next((n for n in nodes if n['name'] == 'declared_opt'), None)
print(opt['status'] if opt else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_OPT" = "missing" ]; then
    echo "ok (r3): declared_opt status is 'missing'"
  else
    echo "FAIL (r3): declared_opt status is '$BT_OPT' (expected 'missing')" >&2
    FAIL=1
  fi

  # (r4) extra_unknown has status "unknown" and required null
  BT_UNK=$(echo "$BT_OUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
nodes = d['roots'][0]['nodes']
unk = next((n for n in nodes if n['name'] == 'extra_unknown'), None)
print('{},{}'.format(unk['status'] if unk else 'NOT_FOUND', unk['required'] if unk else 'X'))
" 2>/dev/null)
  if [ "$BT_UNK" = "unknown,None" ]; then
    echo "ok (r4): extra_unknown status is 'unknown' with required null"
  else
    echo "FAIL (r4): extra_unknown is '$BT_UNK' (expected 'unknown,None')" >&2
    FAIL=1
  fi
fi

# (s) audit mode: missing required emits error; unknown emits warn; no findings for optional-missing
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  BT_AUDIT=$(bash "$SCRIPT" --repo-root "$BT_TMP" --audit 2>/dev/null)

  # s1: findings array exists
  HAS_FINDINGS=$(echo "$BT_AUDIT" | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if 'findings' in d else 'no')" 2>/dev/null)
  if [ "$HAS_FINDINGS" = "yes" ]; then
    echo "ok (s1): audit output has findings array"
  else
    echo "FAIL (s1): audit output missing findings array" >&2
    FAIL=1
  fi

  # s2: missing required declared_req → severity error, type missing_required
  BT_S2=$(echo "$BT_AUDIT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
f = next((x for x in d['findings'] if x['type'] == 'missing_required' and 'declared_req' in x['path']), None)
print(f['severity'] if f else 'NOT_FOUND')
" 2>/dev/null)
  if [ "$BT_S2" = "error" ]; then
    echo "ok (s2): missing required node emits severity 'error'"
  else
    echo "FAIL (s2): missing_required finding not found or wrong severity (got: '$BT_S2')" >&2
    FAIL=1
  fi

  # s3: unknown extra_unknown → severity warn, type unknown
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

  # s4: missing optional declared_opt → NO finding (optional missing is not a deviation)
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

# (t) user project with no declaration → root entry has declaration "missing"
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

# (u) --audit emits missing_declaration warn for user project without workspace-structure.json
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
```

- [ ] **Step 2: Run test to verify all new checks fail**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep -E "^(ok|FAIL) \([r-u]\)"
```

Expected: FAIL on r1 (schemaVersion), likely errors on others.

- [ ] **Step 3: Rewrite `workspace-map.sh`**

Replace the full contents of `.claude/features/contract/scripts/workspace-map.sh`:

```bash
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
# Version: 2.0.0
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
# Parse flags for show/audit/human mode
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

python3 << PYEOF
import json, os, sys

REPO_ROOT = "$REPO_ROOT"
HUMAN = $HUMAN
AUDIT = $AUDIT
CLAUDE_DIR = os.path.join(REPO_ROOT, ".claude")

def load_declaration(filepath):
    if not os.path.isfile(filepath):
        return None
    try:
        d = json.load(open(filepath))
        for req in ("schema_version", "owner", "root", "nodes"):
            if req not in d:
                return None
        return d
    except Exception:
        return None

def walk_nodes(declared_nodes, fs_path):
    declared_names = {n["name"] for n in declared_nodes}
    try:
        actual_dirs = {e for e in os.listdir(fs_path)
                       if os.path.isdir(os.path.join(fs_path, e))}
    except Exception:
        actual_dirs = set()
    result = []
    for node in declared_nodes:
        node_fs = os.path.join(fs_path, node["name"])
        status = "present" if os.path.isdir(node_fs) else "missing"
        children = walk_nodes(node.get("children", []), node_fs) if status == "present" else []
        result.append({
            "name": node["name"],
            "required": node["required"],
            "description": node.get("description", ""),
            "status": status,
            "children": children,
        })
    for name in sorted(actual_dirs - declared_names):
        if name.startswith("."):
            continue
        result.append({
            "name": name,
            "required": None,
            "description": "",
            "status": "unknown",
            "children": [],
        })
    return result

def collect_findings(nodes, path_prefix, root_name):
    findings = []
    for node in nodes:
        full = os.path.join(path_prefix, node["name"])
        if node["status"] == "missing" and node["required"] is True:
            findings.append({"severity": "error", "type": "missing_required", "path": full, "root": root_name})
        elif node["status"] == "unknown":
            findings.append({"severity": "warn", "type": "unknown", "path": full, "root": root_name})
        if node.get("children"):
            findings.extend(collect_findings(node["children"], full, root_name))
    return findings

def print_nodes_human(nodes, indent):
    for node in nodes:
        req_label = "[required]" if node["required"] is True else ("[optional]" if node["required"] is False else "[UNKNOWN] ")
        status_label = node["status"].upper()
        print("{}  {}/  {}  {}".format("  " * indent, node["name"], req_label, status_label))
        if node.get("children"):
            print_nodes_human(node["children"], indent + 1)

# --- Rabbit root ---
rabbit_decl = load_declaration(os.path.join(CLAUDE_DIR, "workspace-structure.json"))
rabbit_nodes = walk_nodes(rabbit_decl["nodes"], CLAUDE_DIR) if rabbit_decl else []
rabbit_root = {
    "root": rabbit_decl["root"] if rabbit_decl else "rabbit",
    "path": ".claude",
    "declaration": "found" if rabbit_decl else "missing",
    "nodes": rabbit_nodes,
}

# --- User project roots ---
user_roots = []
try:
    entries = sorted(
        e for e in os.listdir(REPO_ROOT)
        if not e.startswith(".") and os.path.isdir(os.path.join(REPO_ROOT, e))
    )
except Exception:
    entries = []

for entry in entries:
    proj_path = os.path.join(REPO_ROOT, entry)
    proj_decl = load_declaration(os.path.join(proj_path, "workspace-structure.json"))
    if proj_decl:
        nodes = walk_nodes(proj_decl["nodes"], proj_path)
        user_roots.append({"root": proj_decl["root"], "path": entry, "declaration": "found", "nodes": nodes})
    else:
        user_roots.append({"root": entry, "path": entry, "declaration": "missing", "nodes": []})

all_roots = [rabbit_root] + user_roots

# --- Audit findings ---
all_findings = []
if AUDIT:
    if rabbit_decl is None:
        all_findings.append({"severity": "warn", "type": "missing_declaration", "path": ".claude", "root": "rabbit"})
    else:
        all_findings.extend(collect_findings(rabbit_nodes, ".claude", rabbit_root["root"]))
    for r in user_roots:
        if r["declaration"] == "missing":
            all_findings.append({"severity": "warn", "type": "missing_declaration", "path": r["path"], "root": r["root"]})
        else:
            all_findings.extend(collect_findings(r["nodes"], r["path"], r["root"]))

# --- Output ---
if HUMAN:
    if AUDIT:
        print("=== rabbit workspace audit ===")
        if not all_findings:
            print("  no deviations found")
        for f in all_findings:
            sev = "ERROR" if f["severity"] == "error" else "WARN "
            print("  {}  {}  {}".format(sev, f["type"], f["path"]))
    else:
        print("=== rabbit workspace map ===")
        print("repo: {}".format(REPO_ROOT))
        print()
        for r in all_roots:
            print("--- {} [{}] ({}) ---".format(r["root"], r["declaration"], r["path"]))
            print_nodes_human(r["nodes"], 0)
            print()
else:
    if AUDIT:
        print(json.dumps({"schemaVersion": "2.0.0", "findings": all_findings}, indent=2))
    else:
        print(json.dumps({"schemaVersion": "2.0.0", "repoRoot": REPO_ROOT, "roots": all_roots}, indent=2))
PYEOF
```

- [ ] **Step 4: Run all tests**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1
```

Expected: all checks pass. If any fail, fix before committing.

- [ ] **Step 5: Verify old consumer tests still pass**

```bash
bash .claude/features/rabbit-backlog/test/test-workspace-map-invocation.sh 2>&1 | tail -3
bash .claude/features/rabbit-bug/test/test-bug-workspace-map.sh 2>&1 | tail -3
bash .claude/features/rabbit-cage/test/test-rabbit-workspace-map-wiring.sh 2>&1 | tail -3
```

Expected: all three end with `0 failed`.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/scripts/workspace-map.sh \
        .claude/features/contract/test/test-workspace-map.sh
git commit -m "feat(contract): rewrite workspace-map.sh as contract-driven hierarchy map (v2)"
```

---

## Task 5: Add remaining test checks for audit mode and SKILL.md

**Files:**
- Modify: `.claude/features/contract/test/test-workspace-map.sh`

Check (c) was already updated in Task 3. This task adds (v), (w), and extends (h) for `--audit` and `--audit --human` output, and for SKILL.md referencing `--audit`.

- [ ] **Step 1: Update check (d) to also verify v2 shape**

Find the block `# (d) workspace-map.sh produces valid JSON without flags` and replace it:

```bash
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
```

- [ ] **Step 2: Add check (v) for `--audit` producing valid JSON with findings key**

```bash
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
```

- [ ] **Step 3: Add check (w) for `--audit --human` producing non-JSON output**

```bash
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
```

- [ ] **Step 4: Add check for SKILL.md referencing `--audit`**

Find the `# (h) SKILL.md references workspace-map.sh and the --human flag` block and add after it:

```bash
  if ! grep -q -- "--audit" "$SKILL_MD"; then
    echo "FAIL (h): SKILL.md does not reference --audit flag" >&2
    FAIL=1
  else
    echo "ok (h3): SKILL.md references --audit flag"
  fi
```

- [ ] **Step 5: Run full test suite**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1
```

Expected: all checks pass. If check (h3) fails, that is expected — it will be fixed in Task 6 when SKILL.md is updated.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/test/test-workspace-map.sh
git commit -m "test(contract): update workspace-map tests for v2 output (roots/findings/audit)"
```

---

## Task 6: Update `rabbit-workspace-map` SKILL.md

**Files:**
- Modify: `.claude/features/contract/skills/rabbit-workspace-map/SKILL.md`
- Sync: `.claude/skills/rabbit-workspace-map/SKILL.md`

- [ ] **Step 1: Verify check (h3) fails against old SKILL.md**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1 | grep "(h3)"
```

Expected: `FAIL (h3): SKILL.md does not reference --audit flag`

- [ ] **Step 2: Replace SKILL.md source**

Write `.claude/features/contract/skills/rabbit-workspace-map/SKILL.md`:

```markdown
---
name: rabbit-workspace-map
description: Use when the user asks to see, inspect, understand, or audit the rabbit-workflow workspace layout — the structural hierarchy of rabbit root and user project roots, based on workspace-structure.json declarations. Trigger phrases include "show the workspace map", "workspace overview", "workspace structure", "audit the workspace", "check workspace conformance", "what's out of contract", or any question requiring workspace hierarchy. Use --human when the user wants a readable terminal view; --audit when checking conformance; default JSON output for machine/programmatic use.
---

# rabbit-workspace-map skill

Execute `.claude/features/contract/scripts/workspace-map.sh` immediately on invocation. Do not describe it, do not paraphrase its output — run it.

## Action

Run one of the following, based on what the user wants:

- User wants to **see** the map (human-readable):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh --human
  ```

- User wants to **process** the map (JSON for machine/programmatic use):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh
  ```

- User wants to **audit** conformance (human-readable findings):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh --audit --human
  ```

- User wants to **audit** conformance (machine-oriented findings):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh --audit
  ```

The default JSON output conforms to `.claude/features/contract/schemas/workspace-map.json.schema.json` (v2.0.0) with a `roots` array. Audit mode emits a `findings` array of deviations.

## Mode Selection

| User signal | Command |
|-------------|---------|
| "show me", "what's in the workspace", "workspace overview", "workspace structure" | `--human` |
| "give me JSON", "pipe to jq", "filter ... where", chained tooling | default JSON (omit `--human`) |
| "audit", "check conformance", "what's out of contract" (human) | `--audit --human` |
| "audit", "check conformance", "what's out of contract" (machine) | `--audit` |

If unsure between show and audit, prefer `--human` for overviews, `--audit` for correctness checks.

## Do Not

- Do not re-implement the workspace walk inline (no ad-hoc `find` / `ls` loops). Always invoke `workspace-map.sh`.
- Do not call `.claude/skills/rabbit-workspace-map/...` as a script — that path holds only this SKILL.md. The executable lives under `.claude/features/contract/scripts/`.
- Do not dump raw JSON to a user who asked to *see* the map; use `--human`.
- Do not run `--audit` when the user asked for an overview; do not omit `--audit` when the user asked for conformance checking.
```

- [ ] **Step 3: Sync deployed copy**

```bash
cp .claude/features/contract/skills/rabbit-workspace-map/SKILL.md \
   .claude/skills/rabbit-workspace-map/SKILL.md
```

- [ ] **Step 4: Run full test suite**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1
```

Expected: all checks pass including (h3) and (j) (deployed copy in sync).

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/skills/rabbit-workspace-map/SKILL.md \
        .claude/skills/rabbit-workspace-map/SKILL.md
git commit -m "feat(contract): update rabbit-workspace-map SKILL.md for v2 (add --audit mode)"
```

---

## Final Verification

- [ ] **Run all contract feature tests**

```bash
bash .claude/features/contract/test/test-workspace-map.sh 2>&1
```

Expected: all checks pass.

- [ ] **Run all consumer tests**

```bash
bash .claude/features/rabbit-backlog/test/test-workspace-map-invocation.sh 2>&1 | tail -3
bash .claude/features/rabbit-bug/test/test-bug-workspace-map.sh 2>&1 | tail -3
bash .claude/features/rabbit-cage/test/test-rabbit-workspace-map-wiring.sh 2>&1 | tail -3
```

Expected: all three report 0 failures.

- [ ] **Live smoke test (show mode human)**

```bash
.claude/features/contract/scripts/workspace-map.sh --human
```

Expected: readable tree with rabbit root nodes annotated present/missing/unknown.

- [ ] **Live smoke test (audit mode human)**

```bash
.claude/features/contract/scripts/workspace-map.sh --audit --human
```

Expected: list of deviations (any unknown dirs, any missing required nodes) or "no deviations found".
