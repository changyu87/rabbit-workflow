# Rabbit Workflow Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Bootstrapping note:** This plan redesigns the rabbit-workflow dispatch system itself. Use the CURRENT (pre-redesign) feature-touch skill and dispatch scripts during implementation. Do NOT attempt to use the new system to build itself.
>
> **Skill deployment:** Skills are deployed via `build-contract.json` copy-file entries (not manual cp). Any new skill requires a new entry in `.claude/features/contract/build-contract.json`.

**Goal:** Redesign rabbit-workflow so TDD is a standard subagent callable from any skill, bug/backlog skills have full TDD integration via a contracted handoff, scope resolution is a shared skill, and the registry is distributed across feature.json files.

**Architecture:** Four sequential phases — Foundation (distributed registry, TDD state prune, CLAUDE.md pointer, R7 gate, session-init cleanup), rabbit-feature-scope skill, revised feature-touch + TDD subagent, revised bug/backlog skills. Each phase is fully testable before the next begins.

**Tech Stack:** Bash, Python 3, jq, git, GitHub CLI (gh)

---

## File Map

### Phase 1 — Foundation

**New:**
- `.claude/features/contract/scripts/find-feature.sh`

**Modified:**
- `.claude/features/tdd-state-machine/scripts/tdd-step.sh`
- `.claude/features/tdd-state-machine/scripts/tdd-context.sh`
- `.claude/features/contract/scripts/dispatch-feature-edit.sh`
- `.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh`
- `.claude/features/contract/scripts/dispatch-spec-update.sh`
- `.claude/features/rabbit-bug/scripts/file-bug.sh`
- `.claude/features/rabbit-backlog/scripts/file-backlog-item.sh`
- `.claude/features/rabbit-cage/hooks/scope-guard.sh` (source) + `.claude/hooks/scope-guard.sh` (deployed copy)
- `.claude/features/rabbit-bug/scripts/bug-status.sh`
- `.claude/features/contract/build-contract.json`
- `CLAUDE.md`
- `.claude/features/rabbit-cage/hooks/session-init.sh` (source) + `.claude/hooks/session-init.sh` (deployed copy)
- `.claude/workspace-structure.json`
- `.gitignore`

**Deleted:**
- `.claude/features/registry.json`
- `.claude/features/contract/scripts/rebuild-registry.sh`
- `.claude/features/rabbit-cage/scripts/generate-claude-md.sh`
- `.claude/features/tdd-state-machine/scripts/resolve-feature-scope.sh`

**Tests updated:**
- `.claude/features/contract/test/test-files-exist.sh`
- `.claude/features/tdd-state-machine/test/test-tdd-step.sh`

### Phase 2 — rabbit-feature-scope

**New:**
- `.claude/features/rabbit-feature-scope/feature.json`
- `.claude/features/rabbit-feature-scope/docs/spec/spec.md`
- `.claude/features/rabbit-feature-scope/docs/spec/contract.md`
- `.claude/features/rabbit-feature-scope/scripts/resolve-scope.sh`
- `.claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md`
- `.claude/features/rabbit-feature-scope/test/run.sh`
- `.claude/features/rabbit-feature-scope/test/test-resolve-scope.sh`
- `.claude/skills/rabbit-feature-scope/SKILL.md` (deployed)

**Modified:**
- `.claude/features/contract/build-contract.json` (add rabbit-feature-scope entry)
- `.claude/workspace-structure.json` (add rabbit-feature-scope node — already done in Phase 1)

### Phase 3 — feature-touch + TDD subagent

**Modified:**
- `.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh`
- `.claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md`
- `.claude/skills/rabbit-feature-touch/SKILL.md` (deployed — updated via build-contract.json)

### Phase 4 — rabbit-bug + rabbit-backlog

**Modified:**
- `.claude/features/rabbit-backlog/scripts/backlog-item-status.sh`
- `.claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md`
- `.claude/skills/rabbit-bug/SKILL.md` (deployed)
- `.claude/features/rabbit-backlog/skills/rabbit-backlog/SKILL.md`
- `.claude/skills/rabbit-backlog/SKILL.md` (deployed)

**New tests:**
- `.claude/features/rabbit-bug/test/test-tdd-report-gate.sh`
- `.claude/features/rabbit-backlog/test/test-tdd-report-backlog.sh`

---

## Phase 1: Foundation

### Task 1: Write tests for `find-feature.sh`

**Files:**
- Create: `.claude/features/contract/test/test-find-feature.sh`

- [ ] **Step 1: Create the failing test file**

```bash
#!/bin/bash
# test-find-feature.sh — tests for distributed feature registry lookup
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# Test 1: script exists and is executable
[ -x "$SCRIPT" ] && ok "script is executable" || fail "script not executable or missing"

# Test 2: find a known feature by name returns a path containing that name
result=$("$SCRIPT" contract 2>/dev/null)
echo "$result" | grep -q "features/contract" && ok "find contract returns correct path" || fail "find contract: got '$result'"

# Test 3: unknown feature exits 1
"$SCRIPT" no-such-feature 2>/dev/null; code=$?
[ "$code" -eq 1 ] && ok "unknown feature exits 1" || fail "unknown feature exit code: $code"

# Test 4: --list includes all known features
list=$("$SCRIPT" --list 2>/dev/null)
for fname in contract policy rabbit-bug rabbit-backlog rabbit-cage tdd-state-machine; do
  echo "$list" | grep -q "^${fname}$" && ok "--list includes $fname" || fail "--list missing $fname"
done

# Test 5: --list-json is a valid JSON array
json=$("$SCRIPT" --list-json 2>/dev/null)
echo "$json" | python3 -c "import json,sys; a=json.load(sys.stdin); assert isinstance(a,list)" 2>/dev/null \
  && ok "--list-json is valid JSON array" || fail "--list-json not valid JSON"

# Test 6: --list-json entries have required fields (name, path, summary, tdd_state)
echo "$json" | python3 -c "
import json, sys
a = json.load(sys.stdin)
for e in a:
    for f in ('name','path','summary','tdd_state'):
        assert f in e, f'missing field {f} in {e}'
" 2>/dev/null && ok "--list-json entries have all required fields" || fail "--list-json entries missing fields"

# Test 7: returned path exists on disk
path=$("$SCRIPT" contract 2>/dev/null)
[ -d "$REPO_ROOT/$path" ] && ok "returned path exists on disk" || fail "path not on disk: $REPO_ROOT/$path"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
bash .claude/features/contract/test/test-find-feature.sh
```

Expected: FAIL on "script not executable or missing" and all subsequent tests.

- [ ] **Step 3: Commit the test**

```bash
git add .claude/features/contract/test/test-find-feature.sh
git commit -m "test(contract): add failing tests for find-feature.sh"
```

---

### Task 2: Implement `find-feature.sh`

**Files:**
- Create: `.claude/features/contract/scripts/find-feature.sh`

- [ ] **Step 1: Create the script**

```bash
#!/bin/bash
# find-feature.sh — distributed feature registry lookup.
# Replaces registry.json as the authoritative feature index.
#
# Usage:
#   find-feature.sh <feature-name>   # print relative path to feature dir; exit 1 if not found
#   find-feature.sh --list            # print all feature names, one per line
#   find-feature.sh --list-json       # print [{name,path,summary,tdd_state},...] as JSON
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when feature discovery is handled natively by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$REPO_ROOT" ] && { echo "ERROR: cannot determine repo root" >&2; exit 1; }

CMD="${1:-}"

case "$CMD" in
  --list)
    for fj in "$REPO_ROOT/.claude/features"/*/feature.json; do
      [ -f "$fj" ] || continue
      python3 -c "import json; print(json.load(open('$fj')).get('name',''))" 2>/dev/null | grep -v '^$' || true
    done
    for proj_feats in "$REPO_ROOT"/*/features; do
      [ -d "$proj_feats" ] || continue
      for fj in "$proj_feats"/*/feature.json; do
        [ -f "$fj" ] || continue
        python3 -c "import json; print(json.load(open('$fj')).get('name',''))" 2>/dev/null | grep -v '^$' || true
      done
    done
    exit 0
    ;;

  --list-json)
    python3 - "$REPO_ROOT" <<'PYEOF'
import json, os, sys, glob
repo = sys.argv[1]
results = []
# Rabbit-level features
for fj in sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json'))):
    try:
        f = json.load(open(fj))
        results.append({
            'name': f.get('name', ''),
            'path': os.path.relpath(os.path.dirname(fj), repo),
            'summary': f.get('summary', ''),
            'tdd_state': f.get('tdd_state', '')
        })
    except Exception:
        pass
# Project-level features
for entry in sorted(os.listdir(repo)):
    feat_base = os.path.join(repo, entry, 'features')
    if not os.path.isdir(feat_base):
        continue
    for fname in sorted(os.listdir(feat_base)):
        fj = os.path.join(feat_base, fname, 'feature.json')
        if os.path.isfile(fj):
            try:
                f = json.load(open(fj))
                results.append({
                    'name': f.get('name', ''),
                    'path': os.path.relpath(os.path.dirname(fj), repo),
                    'summary': f.get('summary', ''),
                    'tdd_state': f.get('tdd_state', '')
                })
            except Exception:
                pass
print(json.dumps(results))
PYEOF
    exit 0
    ;;

  ""|--help|-h)
    echo "usage: find-feature.sh <feature-name> | --list | --list-json" >&2
    exit 2
    ;;

  -*)
    echo "ERROR: unknown option '$CMD'" >&2
    exit 2
    ;;

  *)
    # Feature name lookup
    FEATURE_NAME="$CMD"
    result=""
    for fj in "$REPO_ROOT/.claude/features"/*/feature.json; do
      [ -f "$fj" ] || continue
      found=$(python3 -c "
import json, os
f = json.load(open('$fj'))
if f.get('name','') == '$FEATURE_NAME':
    print(os.path.relpath(os.path.dirname('$fj'), '$REPO_ROOT'))
" 2>/dev/null)
      if [ -n "$found" ]; then result="$found"; break; fi
    done
    if [ -z "$result" ]; then
      for proj_feats in "$REPO_ROOT"/*/features; do
        [ -d "$proj_feats" ] || continue
        for fj in "$proj_feats"/*/feature.json; do
          [ -f "$fj" ] || continue
          found=$(python3 -c "
import json, os
f = json.load(open('$fj'))
if f.get('name','') == '$FEATURE_NAME':
    print(os.path.relpath(os.path.dirname('$fj'), '$REPO_ROOT'))
" 2>/dev/null)
          if [ -n "$found" ]; then result="$found"; break 2; fi
        done
      done
    fi
    if [ -z "$result" ]; then
      echo "ERROR: feature '$FEATURE_NAME' not found" >&2
      exit 1
    fi
    echo "$result"
    ;;
esac
```

- [ ] **Step 2: Make executable**

```bash
chmod +x .claude/features/contract/scripts/find-feature.sh
```

- [ ] **Step 3: Run tests — all must pass**

```bash
bash .claude/features/contract/test/test-find-feature.sh
```

Expected: all 10 tests pass.

- [ ] **Step 4: Commit**

```bash
git add .claude/features/contract/scripts/find-feature.sh
git commit -m "feat(contract): add find-feature.sh — distributed registry lookup replacing registry.json"
```

---

### Task 3: Prune `review` and `merged` from TDD state machine

**Files:**
- Create: `.claude/features/tdd-state-machine/test/test-tdd-state-prune.sh`
- Modify: `.claude/features/tdd-state-machine/scripts/tdd-step.sh`
- Modify: `.claude/features/tdd-state-machine/scripts/tdd-context.sh`

- [ ] **Step 1: Write the failing test**

```bash
#!/bin/bash
# test-tdd-state-prune.sh — verify review/merged removed; spec-update added to tdd-context.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
TDD_STEP="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-step.sh"
TDD_CTX="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/tdd-context.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# Helpers: create a feature.json with a given tdd_state
make_feature() {
  local dir="$1" state="$2"
  mkdir -p "$dir"
  printf '{"name":"test-prune","tdd_state":"%s","version":"0.1.0","owner":"test","deprecation":{"criterion":"never"}}' "$state" > "$dir/feature.json"
}

# --- tdd-step.sh tests ---

# 1. review is not a valid state (even with --force)
make_feature "$TMPDIR_TEST/f1" test-green
bash "$TDD_STEP" transition "$TMPDIR_TEST/f1" review --force 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "review rejected even with --force" || fail "review should be invalid state"

# 2. merged is not a valid state (even with --force)
make_feature "$TMPDIR_TEST/f2" test-green
bash "$TDD_STEP" transition "$TMPDIR_TEST/f2" merged --force 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "merged rejected even with --force" || fail "merged should be invalid state"

# 3. next from test-green is deprecated
make_feature "$TMPDIR_TEST/f3" test-green
next=$(bash "$TDD_STEP" next "$TMPDIR_TEST/f3" 2>/dev/null)
[ "$next" = "deprecated" ] && ok "next from test-green is deprecated" || fail "next from test-green: expected 'deprecated', got '$next'"

# 4. normal forward chain still works: spec -> spec-update
make_feature "$TMPDIR_TEST/f4" spec
bash "$TDD_STEP" transition "$TMPDIR_TEST/f4" spec-update 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "spec -> spec-update still works" || fail "spec -> spec-update broken"

# --- tdd-context.sh tests ---

# 5. from spec, allowed_next_states = ["spec-update"]
make_feature "$TMPDIR_TEST/f5" spec
ctx=$(bash "$TDD_CTX" "$TMPDIR_TEST/f5" 2>/dev/null)
echo "$ctx" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['allowed_next_states'] == ['spec-update'], f'got {d[\"allowed_next_states\"]}'
" 2>/dev/null && ok "context: spec -> allowed_next = [spec-update]" || fail "context: spec allowed_next wrong"

# 6. from spec-update, allowed_next_states = ["test-red"]
make_feature "$TMPDIR_TEST/f6" spec-update
ctx=$(bash "$TDD_CTX" "$TMPDIR_TEST/f6" 2>/dev/null)
echo "$ctx" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['allowed_next_states'] == ['test-red'], f'got {d[\"allowed_next_states\"]}'
" 2>/dev/null && ok "context: spec-update -> allowed_next = [test-red]" || fail "context: spec-update allowed_next wrong"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/tdd-state-machine/test/test-tdd-state-prune.sh
```

Expected: tests 1–3 fail (review/merged currently valid); tests 5–6 fail (spec-update missing from tdd-context.sh).

- [ ] **Step 3: Update `tdd-step.sh` — remove `review` and `merged`**

In `forward_next()`, replace:
```bash
test-green) echo "review" ;;
review)     echo "merged" ;;
merged)     echo "deprecated" ;;
```
With:
```bash
test-green) echo "deprecated" ;;
```

In `is_valid_state()`, replace:
```bash
spec|spec-update|test-red|impl|test-green|review|merged|deprecated) return 0 ;;
```
With:
```bash
spec|spec-update|test-red|impl|test-green|deprecated) return 0 ;;
```

- [ ] **Step 4: Update `tdd-context.sh` — add `spec-update`**

In `allowed_next()`, replace:
```bash
spec)       echo '["test-red"]' ;;
```
With:
```bash
spec)        echo '["spec-update"]' ;;
spec-update) echo '["test-red"]' ;;
```

In `guidance_for()`, add after the `spec)` case:
```bash
spec-update)
  echo "Update docs/spec/spec.md to describe the planned change. A git diff showing spec edits must be present before transitioning to test-red (or provide --spec-no-change-reason). Then transition to test-red." ;;
```

Remove `review)` and `merged)` cases from both `allowed_next()` and `guidance_for()`.

- [ ] **Step 5: Run tests — all must pass**

```bash
bash .claude/features/tdd-state-machine/test/test-tdd-state-prune.sh
bash .claude/features/tdd-state-machine/test/run.sh
```

If existing tests reference `review` or `merged` transitions, update those assertions to match the new chain.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/tdd-state-machine/scripts/tdd-step.sh \
        .claude/features/tdd-state-machine/scripts/tdd-context.sh \
        .claude/features/tdd-state-machine/test/test-tdd-state-prune.sh
git commit -m "feat(tdd-state-machine): remove review/merged states; add spec-update to tdd-context.sh"
```

---

### Task 4: Migrate all `registry.json` lookups to `find-feature.sh`

**Files:**
- Modify: `.claude/features/contract/scripts/dispatch-feature-edit.sh`
- Modify: `.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh`
- Modify: `.claude/features/contract/scripts/dispatch-spec-update.sh`
- Modify: `.claude/features/rabbit-bug/scripts/file-bug.sh`
- Modify: `.claude/features/rabbit-backlog/scripts/file-backlog-item.sh`
- Modify: `.claude/features/rabbit-cage/hooks/scope-guard.sh` + `.claude/hooks/scope-guard.sh`

**Pattern:** Every file has one or more of these registry lookups — replace each with a `find-feature.sh` call:

```bash
# BEFORE (pattern A — single feature path lookup):
REGISTRY="$REPO_ROOT/.claude/features/registry.json"
FEATURE_PATH=$(python3 -c "import json; r=json.load(open('$REGISTRY')); \
  print(r.get('features',{}).get('$FEATURE_NAME',{}).get('path',''))" 2>/dev/null)

# AFTER:
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
FEATURE_PATH=$(bash "$FIND_FEATURE" "$FEATURE_NAME" 2>/dev/null)

# BEFORE (pattern B — enumerate feature names):
python3 -c "import json; r=json.load(open('$REGISTRY')); [print(k) for k in r.get('features',{}).keys()]"

# AFTER:
bash "$FIND_FEATURE" --list 2>/dev/null
```

- [ ] **Step 1: Update `dispatch-feature-edit.sh`**

Find the `REGISTRY` variable declaration and the `python3` feature-path lookup block (~lines 42–77). Replace with:

```bash
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
FEATURE_PATH=$(bash "$FIND_FEATURE" "$FEATURE_NAME" 2>/dev/null) || {
  echo "ERROR: feature '$FEATURE_NAME' not found" >&2
  exit 1
}
```

Remove all remaining references to `REGISTRY` and `registry.json` in this file.

- [ ] **Step 2: Update `dispatch-feature-tdd.sh`**

Same replacement — find the `REGISTRY` and `FEATURE_PATH` block near the top, replace with `find-feature.sh` call:

```bash
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
FEATURE_PATH=$(bash "$FIND_FEATURE" "$FEATURE_NAME" 2>/dev/null) || {
  echo "ERROR: feature '$FEATURE_NAME' not found in registry" >&2; exit 1
}
FEATURE_DIR="$REPO_ROOT/$FEATURE_PATH"
```

- [ ] **Step 3: Update `dispatch-spec-update.sh`**

Same pattern — replace the registry lookup for `FEATURE_PATH`.

- [ ] **Step 4: Update `file-bug.sh`**

Find where `--related-feature` is validated against `registry.json`. Replace validation with:

```bash
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
if [ -n "$RELATED_FEATURE" ]; then
  bash "$FIND_FEATURE" "$RELATED_FEATURE" >/dev/null 2>&1 || {
    echo "ERROR: related-feature '$RELATED_FEATURE' not found in feature index" >&2
    exit 1
  }
fi
```

- [ ] **Step 5: Update `file-backlog-item.sh`**

Same pattern as `file-bug.sh` — replace registry validation with `find-feature.sh` check.

- [ ] **Step 6: Update `scope-guard.sh` (both copies)**

Two registry lookups exist in `scope-guard.sh`:

**Lookup 1** — per-feature marker resolution (~line 88–96):
```bash
# BEFORE:
REGISTRY="$REPO_ROOT/.claude/features/registry.json"
per_path=$(python3 -c "import json,sys; r=json.load(open('$REGISTRY')); \
  print(r.get('features',{}).get('$per_feature',{}).get('path',''))" 2>/dev/null)

# AFTER:
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
per_path=$(bash "$FIND_FEATURE" "$per_feature" 2>/dev/null) || true
```

**Lookup 2** — active scope feature path resolution (~line 103–105):
```bash
# BEFORE:
REGISTRY="$REPO_ROOT/.claude/features/registry.json"
FEATURE_PATH=$(python3 -c "import json,sys; r=json.load(open('$REGISTRY')); \
  print(r.get('features',{}).get('$SCOPE_FEATURE',{}).get('path',''))" 2>/dev/null)

# AFTER (FIND_FEATURE already set from lookup 1):
FEATURE_PATH=$(bash "$FIND_FEATURE" "$SCOPE_FEATURE" 2>/dev/null) || true
```

Apply both changes to BOTH files:
- `.claude/features/rabbit-cage/hooks/scope-guard.sh` (source)
- `.claude/hooks/scope-guard.sh` (deployed copy)

- [ ] **Step 7: Run existing test suites — no regression**

```bash
bash .claude/features/contract/test/run.sh
bash .claude/features/rabbit-bug/test/run.sh
bash .claude/features/rabbit-backlog/test/run.sh
bash .claude/features/rabbit-cage/test/run.sh
```

All must pass.

- [ ] **Step 8: Commit**

```bash
git add \
  .claude/features/contract/scripts/dispatch-feature-edit.sh \
  .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh \
  .claude/features/contract/scripts/dispatch-spec-update.sh \
  .claude/features/rabbit-bug/scripts/file-bug.sh \
  .claude/features/rabbit-backlog/scripts/file-backlog-item.sh \
  .claude/features/rabbit-cage/hooks/scope-guard.sh \
  .claude/hooks/scope-guard.sh
git commit -m "refactor: migrate all registry.json lookups to find-feature.sh"
```

---

### Task 5: Delete removed artifacts

**Files deleted:**
- `.claude/features/registry.json`
- `.claude/features/contract/scripts/rebuild-registry.sh`
- `.claude/features/rabbit-cage/scripts/generate-claude-md.sh`
- `.claude/features/tdd-state-machine/scripts/resolve-feature-scope.sh`

- [ ] **Step 1: Remove `rebuild-registry.sh` hook from `tdd-step.sh`**

In `.claude/features/tdd-state-machine/scripts/tdd-step.sh`, the `test-green` post-transition block contains this code (appears in both the normal and `--force` paths — remove from both):

```bash
# REMOVE this entire block (both occurrences):
FEATURES_DIR="$(dirname "$dir")"
REBUILD_SH="$REPO_ROOT/.claude/features/contract/scripts/rebuild-registry.sh"
if [ -f "$REBUILD_SH" ]; then
  bash "$REBUILD_SH" "$FEATURES_DIR" >/dev/null 2>&1 || true
fi
```

- [ ] **Step 2: Remove `generate-claude-md` entry from `build-contract.json`**

In `.claude/features/contract/build-contract.json`, remove the target with `"type": "generate-claude-md"`:

```json
// REMOVE this entire object:
{
  "name": "CLAUDE.md",
  "type": "generate-claude-md",
  "destination": "CLAUDE.md",
  "check_on_stop": true
}
```

- [ ] **Step 3: Git-remove the deleted files**

```bash
git rm \
  .claude/features/registry.json \
  .claude/features/contract/scripts/rebuild-registry.sh \
  .claude/features/rabbit-cage/scripts/generate-claude-md.sh \
  .claude/features/tdd-state-machine/scripts/resolve-feature-scope.sh
```

- [ ] **Step 4: Update `test-files-exist.sh` for contract feature**

In `.claude/features/contract/test/test-files-exist.sh`:

```bash
# REMOVE any line asserting rebuild-registry.sh exists
# ADD:
[ -f "$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh" ] \
  || fail "find-feature.sh missing"
[ ! -f "$REPO_ROOT/.claude/features/registry.json" ] \
  || fail "registry.json should not exist (distributed registry design)"
```

- [ ] **Step 5: Run tests**

```bash
bash .claude/features/contract/test/run.sh
bash .claude/features/tdd-state-machine/test/run.sh
```

Fix any tests that asserted existence of deleted files.

- [ ] **Step 6: Commit**

```bash
git add \
  .claude/features/tdd-state-machine/scripts/tdd-step.sh \
  .claude/features/contract/build-contract.json \
  .claude/features/contract/test/test-files-exist.sh
git commit -m "feat: delete registry.json, rebuild-registry.sh, generate-claude-md.sh, resolve-feature-scope.sh; remove post-test-green registry rebuild hook"
```

---

### Task 6: Convert CLAUDE.md, clean session-init, update .gitignore

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.claude/features/rabbit-cage/hooks/session-init.sh` + `.claude/hooks/session-init.sh`
- Modify: `.gitignore`
- Modify: `.claude/workspace-structure.json`

- [ ] **Step 1: Identify current policy source files**

```bash
ls .claude/features/policy/
```

Expected output includes: `philosophy.md`, `spec-rules.md`, `coding-rules.md`, `workflow-rules.md`

- [ ] **Step 2: Rewrite `CLAUDE.md` as pure pointer**

Replace the entire content of `CLAUDE.md` with:

```markdown
# Rabbit Workflow — subagent-driven development; every feature touch must invoke the rabbit-feature-touch skill to advance the full TDD state machine before the user decides on each dispatch.

@.claude/features/policy/philosophy.md
@.claude/features/policy/spec-rules.md
@.claude/features/policy/coding-rules.md
@.claude/features/policy/workflow-rules.md
```

The one-line summary at the top is kept — it's the CLAUDE.md title shown by Claude Code.

- [ ] **Step 3: Remove inline section injection from `session-init.sh`**

In both `.claude/features/rabbit-cage/hooks/session-init.sh` and `.claude/hooks/session-init.sh`, remove the entire inline section block:

```bash
# REMOVE this entire block:
INLINE=$(sed -n '/rabbit-policy-start/,/rabbit-policy-end/p' "$CLAUDE_MD" 2>/dev/null | \
  grep -v 'rabbit-policy-start\|rabbit-policy-end' || true)

if [ -n "$INLINE" ]; then
    python3 -c "
import json, sys
payload = sys.stdin.read()
print(json.dumps({
    'additionalContext': payload,
    'systemMessage': '...'
}))
" <<< "$INLINE"
    exit 0
fi
```

Only the `@-import` parsing path (the `imports=$(grep -oE '^@...' ...)` block) remains.

- [ ] **Step 4: Remove R1 branch creation block from `session-init.sh`**

In both copies, remove:

```bash
# REMOVE this entire block:
_current_branch="$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)"
if [ "$_current_branch" = "main" ] || [ "$_current_branch" = "master" ]; then
    _new_branch="session/$(date +%Y%m%d-%H%M%S)"
    git -C "$REPO_ROOT" checkout -b "$_new_branch" >/dev/null 2>&1
    printf '\x1b[32m✅ ━━━ [rabbit] R1: created branch %s ━━━ ✅\x1b[0m\n' "$_new_branch" >&2
fi
```

- [ ] **Step 5: Add `.gitignore` entries**

```bash
printf '\n# Ephemeral TDD artifacts\ntdd-report.json\n.claude/tdd-report.json\n' >> .gitignore
```

- [ ] **Step 6: Add `rabbit-feature-scope` to `workspace-structure.json`**

In `.claude/workspace-structure.json`, add to the `features.children` array:

```json
{ "name": "rabbit-feature-scope", "required": true, "description": "shared skill for resolving natural-language requests to affected rabbit features", "children": [] }
```

- [ ] **Step 7: Run session-init tests**

```bash
bash .claude/features/rabbit-cage/test/run.sh 2>&1 | tail -30
```

Update any tests that checked for the inline section block or the `session/` branch creation.

- [ ] **Step 8: Smoke test `@-import` injection still works**

```bash
bash .claude/hooks/session-init.sh < /dev/null 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'additionalContext' in d
print('PASS: @-import injection works')
"
```

- [ ] **Step 9: Commit**

```bash
git add CLAUDE.md \
        .claude/features/rabbit-cage/hooks/session-init.sh \
        .claude/hooks/session-init.sh \
        .gitignore \
        .claude/workspace-structure.json
git commit -m "feat: CLAUDE.md pure @-import pointer; remove R1 session/ branch creation; add tdd-report.json to .gitignore"
```

---

### Task 7: Update `bug-status.sh` — R7 gate + `--tdd-report` flag

**Files:**
- Create: `.claude/features/rabbit-bug/test/test-tdd-report-gate.sh`
- Modify: `.claude/features/rabbit-bug/scripts/bug-status.sh`

- [ ] **Step 1: Write the failing test**

```bash
#!/bin/bash
# test-tdd-report-gate.sh — verify --tdd-report flag and updated R7 gate
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-bug/scripts/bug-status.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
BUG_DIR="$TMPDIR_TEST/RABBIT-BUG-99"
mkdir -p "$BUG_DIR"

reset_bug() {
  printf '{"id":"RABBIT-BUG-99","title":"test bug","severity":"low","status":"open","history":[]}' \
    > "$BUG_DIR/bug.json"
}

reset_bug

# 1. close fails without vet-triage.json (baseline R7 still works)
bash "$SCRIPT" set "$BUG_DIR" closed --reason "fix" 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "close fails without vet-triage.json" || fail "should fail without vet-triage.json"

# 2. close fails with vet-triage.json but no --tdd-report
touch "$BUG_DIR/vet-triage.json"
bash "$SCRIPT" set "$BUG_DIR" closed --reason "fix" 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "close fails without --tdd-report" || fail "should fail without --tdd-report"

# 3. close succeeds with vet-triage.json + --tdd-report
cat > "$TMPDIR_TEST/tdd-report.json" <<'JSON'
{"schema_version":"1.0.0","feature":"test","test_result":"pass","tdd_state":"test-green",
 "impl_summary":"fixed","spec_compliance":"pass","test_gap_analysis":"none","impl_commit":"abc123"}
JSON
bash "$SCRIPT" set "$BUG_DIR" closed \
  --reason "TDD cycle complete" \
  --tdd-report "$TMPDIR_TEST/tdd-report.json" \
  --fix-commits "abc123" 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "close succeeds with vet-triage.json + --tdd-report" || fail "close failed: exit $code"

# 4. bug.json history contains tdd_report field
has_rpt=$(python3 -c "
import json
h = json.load(open('$BUG_DIR/bug.json'))['history']
print('yes' if h and 'tdd_report' in h[-1] else 'no')
" 2>/dev/null)
[ "$has_rpt" = "yes" ] && ok "bug.json history has tdd_report field" || fail "bug.json missing tdd_report in history"

# 5. tdd-gap.json is NOT required (old requirement removed)
reset_bug
touch "$BUG_DIR/vet-triage.json"
rm -f "$BUG_DIR/tdd-gap.json"
bash "$SCRIPT" set "$BUG_DIR" closed \
  --reason "fix" \
  --tdd-report "$TMPDIR_TEST/tdd-report.json" \
  --fix-commits "abc123" 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "tdd-gap.json not required" || fail "should not require tdd-gap.json: exit $code"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/rabbit-bug/test/test-tdd-report-gate.sh
```

Expected: tests 2, 3, 4, 5 fail.

- [ ] **Step 3: Add `--tdd-report` flag to `bug-status.sh`**

In the `set` subcommand flag-parsing loop, add:

```bash
--tdd-report) tdd_report_path="$2"; shift 2 ;;
```

And initialize at the top of the `set` block:

```bash
tdd_report_path=""
```

- [ ] **Step 4: Update the `closed` R7 gate in `bug-status.sh`**

Replace the current R7 check for `closed` status (the block that checks `vet-triage.json` and `tdd-gap.json`):

```bash
# REMOVE old gate:
elif [ ! -f "$dir/vet-triage.json" ] && [ ! -f "$dir/tdd-gap.json" ]; then
    echo "ERROR (R7): cannot close without vet artifact" 1>&2; exit 1
fi

# ADD new gate:
if [ -n "$skip_vet_reason" ]; then
    note="[skip-vet: $skip_vet_reason] $note"
else
    [ -f "$dir/vet-triage.json" ] || {
        echo "ERROR (R7): vet-triage.json missing — run rabbit-triage.sh first, or use --skip-vet-reason" >&2
        exit 1
    }
    [ -n "$tdd_report_path" ] || {
        echo "ERROR (R7): --tdd-report <path> required to close bug" >&2
        exit 1
    }
    [ -f "$tdd_report_path" ] || {
        echo "ERROR: tdd-report file not found: $tdd_report_path" >&2
        exit 1
    }
fi
```

- [ ] **Step 5: Embed tdd_report into the `closed` history entry**

In the `jq` call that writes the `closed` history entry, add the `tdd_report` field.

Find the existing `jq` block for `closed` and update it:

```bash
# Read tdd_report JSON (null if not provided)
tdd_report_json="null"
if [ -n "$tdd_report_path" ] && [ -f "$tdd_report_path" ]; then
    tdd_report_json=$(cat "$tdd_report_path")
fi

# In the jq update, add tdd_report to the appended history entry:
jq --arg s "$new" --arg ts "$TS" --arg actor "$actor" --arg note "$note" \
   --arg fc "$fix_commits" --arg tf "$touched_files" \
   --argjson rpt "$tdd_report_json" \
   '.history += [{"status":$s,"at":$ts,"actor":$actor,"note":$note,
                  "fix_commits":$fc,"touched_files":$tf,"tdd_report":$rpt}] | .status = $s' \
   "$dir/bug.json" > "$dir/bug.json.tmp" && mv "$dir/bug.json.tmp" "$dir/bug.json"
```

Remove any remaining reference to `tdd-gap.json` in the file.

- [ ] **Step 6: Run all tests**

```bash
bash .claude/features/rabbit-bug/test/test-tdd-report-gate.sh
bash .claude/features/rabbit-bug/test/run.sh
```

- [ ] **Step 7: Commit**

```bash
git add \
  .claude/features/rabbit-bug/scripts/bug-status.sh \
  .claude/features/rabbit-bug/test/test-tdd-report-gate.sh
git commit -m "feat(rabbit-bug): add --tdd-report flag; update R7 gate to check tdd_report field; remove tdd-gap.json requirement"
```

---

## Phase 2: `rabbit-feature-scope` Skill

### Task 8: Scaffold `rabbit-feature-scope` feature

**Files:**
- Create: `.claude/features/rabbit-feature-scope/feature.json`
- Create: `.claude/features/rabbit-feature-scope/docs/spec/spec.md`
- Create: `.claude/features/rabbit-feature-scope/docs/spec/contract.md`
- Create: `.claude/features/rabbit-feature-scope/test/run.sh`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p .claude/features/rabbit-feature-scope/{docs/spec,scripts,skills/rabbit-feature-scope,test}
```

- [ ] **Step 2: Create `feature.json`**

```json
{
  "name": "rabbit-feature-scope",
  "version": "1.0.0",
  "owner": "rabbit-workflow team",
  "tdd_state": "spec",
  "summary": "Shared skill for resolving natural-language requests to the list of rabbit features whose files will be modified.",
  "status": "active",
  "updated": "2026-05-14",
  "deprecation": {
    "criterion": "When feature-scope resolution is automated natively by the dispatch infrastructure."
  },
  "contract": {
    "reads": ["feature.json files via find-feature.sh --list-json"],
    "writes": ["nothing — emits prompt to stdout only"],
    "invokes": [".claude/features/contract/scripts/find-feature.sh"]
  },
  "surface": {
    "scripts": ["scripts/resolve-scope.sh"],
    "skills": []
  }
}
```

- [ ] **Step 3: Create `docs/spec/spec.md`**

```markdown
---
feature: rabbit-feature-scope
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When feature-scope resolution is automated natively by the dispatch infrastructure.
status: active
---

# rabbit-feature-scope — Spec

## Purpose

Provides `resolve-scope.sh`, which builds a prompt for a default-model Agent to map
a natural-language request to the list of rabbit features whose files the request
will modify. Makes no assumptions about callers or use cases.

## Surface

- `.claude/features/rabbit-feature-scope/scripts/resolve-scope.sh`
- `.claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md`

## Invariants

1. `resolve-scope.sh` emits a prompt to stdout only; it never calls Agent itself.
2. The dispatched Agent uses the default model — no Opus override.
3. The script uses `find-feature.sh --list-json` for feature enumeration; never reads `registry.json`.
4. Agent response JSON schema: `{"features": ["name1", ...], "rationale": "one sentence"}`.
5. `resolve-scope.sh` is executable.
6. An empty `features` list `[]` is a valid response (no features touched).
```

- [ ] **Step 4: Create `docs/spec/contract.md`**

```markdown
# rabbit-feature-scope — Contract

## Inputs
- `$1`: request description string (required)

## Outputs
- stdout: assembled prompt for default-model Agent dispatch
- stderr: status/error messages only
- exit 0: success; exit 2: invocation error

## Agent Response Schema
```json
{"features": ["feature-name-1"], "rationale": "one sentence"}
```

Rules:
- `features` contains only names present in `find-feature.sh --list`
- `rationale` is one sentence max
- Empty `features` list is valid
```

- [ ] **Step 5: Create `test/run.sh`**

```bash
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=0; FAIL=0
for t in "$SCRIPT_DIR"/test-*.sh; do
  [ -f "$t" ] || continue
  if bash "$t"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi
done
echo "Total: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

```bash
chmod +x .claude/features/rabbit-feature-scope/test/run.sh
```

- [ ] **Step 6: Commit scaffold**

```bash
git add .claude/features/rabbit-feature-scope/
git commit -m "feat(rabbit-feature-scope): scaffold feature — feature.json, spec, test runner"
```

---

### Task 9: Implement `resolve-scope.sh` with tests

**Files:**
- Create: `.claude/features/rabbit-feature-scope/test/test-resolve-scope.sh`
- Create: `.claude/features/rabbit-feature-scope/scripts/resolve-scope.sh`

- [ ] **Step 1: Write the failing test**

```bash
#!/bin/bash
# test-resolve-scope.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-feature-scope/scripts/resolve-scope.sh"
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# 1. script exists and is executable
[ -x "$SCRIPT" ] && ok "script executable" || fail "not executable or missing"

# 2. exits 2 with no args
"$SCRIPT" 2>/dev/null; code=$?
[ "$code" -eq 2 ] && ok "exits 2 with no args" || fail "exit code no-args: $code"

# 3. emits non-empty prompt for a request
prompt=$("$SCRIPT" "fix the scope guard bug" 2>/dev/null)
[ -n "$prompt" ] && ok "emits non-empty prompt" || fail "empty prompt"

# 4. prompt includes at least one feature name from find-feature.sh --list
first=$(bash "$FIND_FEATURE" --list 2>/dev/null | head -1)
echo "$prompt" | grep -q "$first" && ok "prompt includes feature name '$first'" || fail "prompt missing feature '$first'"

# 5. prompt includes the request text verbatim
echo "$prompt" | grep -q "fix the scope guard bug" && ok "prompt includes request text" || fail "prompt missing request text"

# 6. prompt specifies the JSON response schema
echo "$prompt" | grep -q '"features"' && ok "prompt specifies JSON schema" || fail "prompt missing JSON schema"

# 7. prompt instructs single-line JSON output
echo "$prompt" | grep -q "single line" && ok "prompt says single-line JSON" || fail "prompt missing single-line instruction"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/rabbit-feature-scope/test/test-resolve-scope.sh
```

Expected: FAIL on test 1 (script missing).

- [ ] **Step 3: Implement `resolve-scope.sh`**

```bash
#!/bin/bash
# resolve-scope.sh — build a prompt that maps a request to affected rabbit features.
#
# Usage:
#   resolve-scope.sh "<request-description>"
#
# Output: assembled prompt to stdout. Caller dispatches with default model.
# Agent response JSON: {"features": ["feat-a"], "rationale": "one sentence"}
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-feature-scope)
# Deprecation criterion: when feature-scope resolution is automated by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"

if [ $# -ne 1 ]; then
  echo "ERROR: usage: resolve-scope.sh <request-description>" >&2
  exit 2
fi

REQUEST="$1"

[ -x "$FIND_FEATURE" ] || { echo "ERROR: find-feature.sh not found: $FIND_FEATURE" >&2; exit 1; }

FEATURE_CONTEXT=$(bash "$FIND_FEATURE" --list-json 2>/dev/null | python3 -c "
import json, sys
features = json.load(sys.stdin)
lines = []
for f in features:
    lines.append(f'Feature: {f[\"name\"]}')
    lines.append(f'  Path: {f[\"path\"]}')
    lines.append(f'  Summary: {f[\"summary\"]}')
    lines.append('')
print('\n'.join(lines))
" 2>/dev/null)

cat <<PROMPT
You are a feature-scope resolver for a rabbit-workflow repository.

Given a natural-language request, identify which features the request targets.
A request targets a feature if the implementation work will modify files within
that feature's directory.

REGISTERED FEATURES:
${FEATURE_CONTEXT}

REQUEST:
${REQUEST}

Respond with ONLY valid JSON on a single line — no markdown, no explanation:
{"features": ["feature-name-1", "feature-name-2"], "rationale": "one sentence"}

Rules:
- Include a feature only if the request requires writing/editing files in that feature's directory.
- If the request touches cross-cutting infrastructure (dispatch scripts, schemas, enforcement), include "contract".
- If the request touches hooks, commands, or skills surface, include "rabbit-cage".
- Omit features whose files will not be modified.
- Return an empty features list [] if no features are targeted.
PROMPT
```

- [ ] **Step 4: Make executable and run tests**

```bash
chmod +x .claude/features/rabbit-feature-scope/scripts/resolve-scope.sh
bash .claude/features/rabbit-feature-scope/test/test-resolve-scope.sh
```

All 7 tests must pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/features/rabbit-feature-scope/scripts/resolve-scope.sh \
        .claude/features/rabbit-feature-scope/test/test-resolve-scope.sh
git commit -m "feat(rabbit-feature-scope): implement resolve-scope.sh with tests"
```

---

### Task 10: Deploy `rabbit-feature-scope` SKILL.md

**Files:**
- Create: `.claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md`
- Create: `.claude/skills/rabbit-feature-scope/SKILL.md`
- Modify: `.claude/features/contract/build-contract.json`

- [ ] **Step 1: Create the SKILL.md**

```markdown
---
name: rabbit-feature-scope
description: Resolve a natural-language request to the list of rabbit features whose files it will modify. Emits a prompt for a default-model Agent; caller parses the JSON response. General-purpose shared skill — no assumptions about callers.
version: 1.0.0
owner: rabbit-feature-scope
deprecation_criterion: when feature-scope resolution is automated natively by the dispatch infrastructure.
---

## Overview

`rabbit-feature-scope` resolves a natural-language request to the set of features
it will modify. It is a general-purpose shared skill — callers and use cases are
not prescribed.

## Usage

```bash
PROMPT=$(bash .claude/features/rabbit-feature-scope/scripts/resolve-scope.sh "<request-description>")
# Dispatch Agent(prompt: PROMPT)   ← default model, no override
# Agent responds with JSON:
# {"features": ["feature-name-1"], "rationale": "one sentence"}
```

## Response Schema

```json
{"features": ["name1", "name2"], "rationale": "one sentence"}
```

- `features`: list of feature names matching `find-feature.sh --list`. May be empty `[]`.
- `rationale`: one sentence explaining the selection.
- The feature list is authoritative — caller does not second-guess it.

## Notes

- `resolve-scope.sh` emits a prompt to stdout only; it does not call Agent itself.
- Uses `find-feature.sh --list-json` — not `registry.json`.
- Default model (no Opus override).
```

- [ ] **Step 2: Create deployed directory and copy**

```bash
mkdir -p .claude/skills/rabbit-feature-scope
cp .claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md \
   .claude/skills/rabbit-feature-scope/SKILL.md
```

- [ ] **Step 3: Add entry to `build-contract.json`**

In `.claude/features/contract/build-contract.json`, add to the `targets` array:

```json
{
  "name": "skills/rabbit-feature-scope/SKILL.md",
  "type": "copy-file",
  "source": ".claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md",
  "destination": ".claude/skills/rabbit-feature-scope/SKILL.md",
  "check_on_stop": true
}
```

- [ ] **Step 4: Advance TDD state and commit**

```bash
bash .claude/features/tdd-state-machine/scripts/tdd-step.sh transition \
  .claude/features/rabbit-feature-scope test-green --force
git add .claude/features/rabbit-feature-scope/ \
        .claude/skills/rabbit-feature-scope/ \
        .claude/features/contract/build-contract.json \
        .claude/features/rabbit-feature-scope/feature.json
git commit -m "feat(rabbit-feature-scope): add and deploy SKILL.md; register in build-contract.json"
```

---

## Phase 3: `rabbit-feature-touch` + TDD Subagent

### Task 11: Revise `dispatch-feature-tdd.sh`

**Files:**
- Create: `.claude/features/tdd-state-machine/test/test-dispatch-tdd-new-interface.sh`
- Modify: `.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh`

- [ ] **Step 1: Write the failing test**

```bash
#!/bin/bash
# test-dispatch-tdd-new-interface.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# 1. --bug flag is rejected (removed in new interface)
"$SCRIPT" contract "test" --bug /tmp/fake 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "--bug flag rejected" || fail "--bug should be rejected"

# 2. --backlog flag is rejected
"$SCRIPT" contract "test" --backlog /tmp/fake 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "--backlog flag rejected" || fail "--backlog should be rejected"

# 3. --linked-item without --item-type is rejected
"$SCRIPT" contract "test" --linked-item /tmp/fake 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "--linked-item without --item-type rejected" || fail "should reject missing --item-type"

# 4. valid basic invocation emits non-empty prompt
prompt=$("$SCRIPT" contract "fix the scope guard" 2>/dev/null)
[ -n "$prompt" ] && ok "basic invocation emits prompt" || fail "empty prompt"

# 5. prompt references tdd-report.json
echo "$prompt" | grep -q "tdd-report.json" && ok "prompt references tdd-report.json" || fail "prompt missing tdd-report.json"

# 6. prompt contains spec_compliance field in schema
echo "$prompt" | grep -q "spec_compliance" && ok "prompt contains spec_compliance" || fail "prompt missing spec_compliance"

# 7. prompt contains test_gap_analysis field
echo "$prompt" | grep -q "test_gap_analysis" && ok "prompt contains test_gap_analysis" || fail "prompt missing test_gap_analysis"

# 8. --linked-item --item-type bug is accepted
prompt2=$("$SCRIPT" contract "test" --linked-item /tmp/fake-bug --item-type bug 2>/dev/null)
[ -n "$prompt2" ] && ok "--linked-item --item-type bug accepted" || fail "--linked-item bug rejected"

# 9. prompt mentions inline spec-review (no nested Agent)
echo "$prompt" | grep -qi "inline\|spec.review\|spec-review" && ok "prompt mentions inline spec-review" || fail "prompt missing inline spec-review instruction"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/tdd-state-machine/test/test-dispatch-tdd-new-interface.sh
```

Expected: tests 1–3 fail (old flags still accepted); tests 5–9 may fail.

- [ ] **Step 3: Rewrite `dispatch-feature-tdd.sh` interface**

Replace the flag-parsing block. **Old flags** (`--bug`, `--backlog`) become errors:

```bash
LINKED_ITEM_DIR=""
ITEM_TYPE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --linked-item)
      [ -z "${2:-}" ] && { echo "ERROR: --linked-item requires a directory argument" >&2; exit 2; }
      LINKED_ITEM_DIR="$2"; shift 2 ;;
    --item-type)
      [ -z "${2:-}" ] && { echo "ERROR: --item-type requires bug|backlog" >&2; exit 2; }
      ITEM_TYPE="$2"; shift 2 ;;
    --bug|--backlog)
      echo "ERROR: $1 is removed. Use --linked-item <dir> --item-type <bug|backlog>" >&2
      exit 2 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [ -n "$LINKED_ITEM_DIR" ] && [ -z "$ITEM_TYPE" ]; then
  echo "ERROR: --linked-item requires --item-type <bug|backlog>" >&2; exit 2
fi
if [ -n "$ITEM_TYPE" ] && [ -z "$LINKED_ITEM_DIR" ]; then
  echo "ERROR: --item-type requires --linked-item <dir>" >&2; exit 2
fi
```

Replace registry lookup with `find-feature.sh`:

```bash
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"
FEATURE_PATH=$(bash "$FIND_FEATURE" "$FEATURE_NAME" 2>/dev/null) || {
  echo "ERROR: feature '$FEATURE_NAME' not found" >&2; exit 1
}
FEATURE_DIR="$REPO_ROOT/$FEATURE_PATH"
```

- [ ] **Step 4: Update the emitted TDD prompt — add inline spec-review and tdd-report.json**

In the `cat <<PROMPT ... PROMPT` block, replace the old `Step 8b` status-update block and the old HANDOFF with:

```
Step 7b: Inline spec-review (performed by you — do NOT dispatch another Agent)
  Read: ${SPEC_PATH}
  Run:  git diff HEAD -- ${FEATURE_DIR}/
  Compare each spec invariant to the implementation diff.
  Produce two values for the tdd-report.json:
    spec_compliance: "pass" if all invariants addressed, "fail" if any are missing
    spec_compliance_notes: list any unaddressed invariants, or null if pass

Step 8: Write tdd-report.json to repo root (gitignored — NEVER commit this file)
  Path: ${REPO_ROOT}/tdd-report.json
  Schema (write exactly this JSON):
  {
    "schema_version": "1.0.0",
    "feature": "${FEATURE_NAME}",
    "request": "<original request text>",
    "linked_item": "${LINKED_ITEM_DIR:-null}",
    "item_type": "${ITEM_TYPE:-null}",
    "spec_changes": "<yes|no>",
    "spec_no_change_reason": "<reason or null>",
    "test_gap_analysis": "<what was missing in test coverage before this fix, or 'none'>",
    "impl_summary": "<one paragraph describing what was implemented>",
    "spec_compliance": "<pass|fail>",
    "spec_compliance_notes": "<unaddressed invariants or null>",
    "test_result": "pass",
    "tdd_state": "test-green",
    "impl_commit": "<output of: git rev-parse HEAD>"
  }

Step 9: Scope marker removed by EXIT trap (fires automatically)
```

Replace the old HANDOFF block with:

```
════════════════════════════════════════════════════════════════════════
HANDOFF (emit when complete)
════════════════════════════════════════════════════════════════════════

HANDOFF:
  feature: ${FEATURE_NAME}
  tdd_state: test-green
  test_result: pass
  spec_compliance: <pass|fail>
  tdd_report_path: ${REPO_ROOT}/tdd-report.json
  notes: <brief summary>
```

Remove the old `STATUS_UPDATE_BLOCK`, `HANDOFF_LINKED_ITEM`, and any post-test-green `bug-status.sh` / `backlog-item-status.sh` calls.

- [ ] **Step 5: Run all tests**

```bash
bash .claude/features/tdd-state-machine/test/test-dispatch-tdd-new-interface.sh
bash .claude/features/tdd-state-machine/test/run.sh
```

- [ ] **Step 6: Commit**

```bash
git add \
  .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh \
  .claude/features/tdd-state-machine/test/test-dispatch-tdd-new-interface.sh
git commit -m "feat(tdd-state-machine): revise dispatch-feature-tdd.sh — unified --linked-item interface, tdd-report.json schema, inline spec-review"
```

---

### Task 12: Revise `rabbit-feature-touch` SKILL.md

**Files:**
- Modify: `.claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md`
- Modify: `.claude/skills/rabbit-feature-touch/SKILL.md`

- [ ] **Step 1: Write test for SKILL.md content**

```bash
#!/bin/bash
# test-rabbit-feature-touch-skill-v3.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL="$REPO_ROOT/.claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

[ -f "$SKILL" ] || { echo "FAIL: SKILL.md missing"; exit 1; }

for phrase in \
  "B/B mode" \
  "feat/<feature-name>" \
  "fix/<bug-id>" \
  "task/<backlog-id>" \
  "filing/" \
  "tdd-report.json" \
  "rabbit-feature-scope" \
  "Unified Five-Step" \
  "scope resolution" \
  "primary.*first" \
  "status: success|failed"
do
  grep -qiE "$phrase" "$SKILL" \
    && ok "SKILL.md contains: $phrase" \
    || fail "SKILL.md missing: $phrase"
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/tdd-state-machine/test/test-rabbit-feature-touch-skill-v3.sh
```

- [ ] **Step 3: Rewrite SKILL.md**

Replace the entire content of `.claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md`:

````markdown
---
name: rabbit-feature-touch
description: Use when any write, edit, delete, or add operation targets a feature directory, or when a new feature is being created. Not for read-only queries, and NOT for metadata-only writes (bug filing, backlog filing). Ensures the formal TDD state machine is advanced via tdd-step.sh on every feature touch.
version: 3.0.0
owner: tdd-state-machine
deprecation_criterion: when dispatch-feature-edit.sh natively enforces tdd-step.sh transitions
---

## Overview

The main session's role is **orchestration only**: resolve scope, create branch,
dispatch TDD subagents, verify HANDOFFs. It does NOT read feature code.

**Two modes:**
- **Normal mode** — invoked directly for a feature work request
- **B/B mode** — invoked by the bug or backlog skill, which passes a bug/item dir

## Unified Five-Step Sequence

All modes follow these five steps. Mode determines branch name and step 5 behaviour.

### Step 1 — Scope Resolution

**Normal mode:** Invoke `rabbit-feature-scope`:
```bash
PROMPT=$(bash .claude/features/rabbit-feature-scope/scripts/resolve-scope.sh "<request>")
# Dispatch Agent(prompt: PROMPT)  — default model
# Parse JSON: {"features": ["feat-a", "feat-b"], "rationale": "..."}
```

**B/B mode:** Skip — feature name comes from `related_feature` in the bug/item JSON:
```bash
FEATURE=$(jq -r '.related_feature' "<bug-or-item-dir>/bug.json")
```

### Step 2 — Create Branch

Create before any dispatch. Never write to main.

| Mode | Branch pattern |
|---|---|
| Normal, single feature | `feat/<feature-name>-<keywords>` |
| Normal, multi-feature | `feat/<primary-feature>-multi-<keywords>` (primary = first feature in scope response) |
| Bug fix (B/B) | `fix/<bug-id>-<keywords>` |
| Backlog task (B/B) | `task/<backlog-id>-<keywords>` |

`<keywords>` = 2–4 words from the request, hyphenated, lowercase.

```bash
git checkout -b <branch-name>
```

### Step 3 — Dispatch TDD Subagents

One subagent per feature. Dispatch all in parallel if multiple features.

```bash
# For each feature:
PROMPT=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh \
  <feature-name> "<request>" \
  [--linked-item <bug-or-item-dir> --item-type <bug|backlog>])
# Dispatch Agent(prompt: PROMPT)
```

Each subagent: sets `.rabbit-scope-active-<feature>`, runs full TDD cycle
(spec-update → test-red → impl → inline spec-review → test-green), writes
`tdd-report.json`, emits HANDOFF.

### Step 4 — Collect and Verify HANDOFFs

Verify each HANDOFF:
- `tdd_state: test-green` for every feature
- `test_result: pass` for every feature
- `spec_compliance: pass` (investigate if fail before proceeding)

If any feature fails: surface failure to user. Do NOT proceed to step 5.

### Step 5 — PR / Hand Off

**Normal mode:**
```bash
gh pr create --title "<summary>" --body "<tdd report highlights>"
```
Summarize the TDD report to the user.

**B/B mode:** Commit code to the branch. Hand off to calling skill:
```
{
  "mode": "bug|backlog",
  "linked_item": "<path>",
  "feature": "<name>",
  "branch": "<branch-name>",
  "tdd_report_path": "<repo-root>/tdd-report.json",
  "status": "success|failed"
}
```

If `status: failed`, calling skill surfaces the failure before any item close.
PR creation is the calling skill's responsibility in B/B mode.

## Red Flags — STOP

- Reading feature code directly in the main session → STOP. Subagent's job.
- Skipping scope resolution in normal mode → STOP.
- Dispatching features sequentially when multiple → STOP. Use parallel.
- HANDOFF shows `tdd_state ≠ test-green` → STOP and investigate.

## Override Path

When user explicitly approves a lightweight edit (typo, comment-only), present
a confirm token with `one-time` or `session` scope. After approval, write
`.rabbit-scope-override`, make the edit directly. Does NOT reset `tdd_state`.
````

- [ ] **Step 4: Copy to deployed location**

```bash
cp .claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md \
   .claude/skills/rabbit-feature-touch/SKILL.md
```

- [ ] **Step 5: Run tests**

```bash
bash .claude/features/tdd-state-machine/test/test-rabbit-feature-touch-skill-v3.sh
bash .claude/features/tdd-state-machine/test/run.sh
```

- [ ] **Step 6: Commit**

```bash
git add \
  .claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md \
  .claude/skills/rabbit-feature-touch/SKILL.md \
  .claude/features/tdd-state-machine/test/test-rabbit-feature-touch-skill-v3.sh
git commit -m "feat(tdd-state-machine): revise rabbit-feature-touch SKILL.md — unified 5-step, B/B mode, branch naming"
```

---

## Phase 4: `rabbit-bug` + `rabbit-backlog`

### Task 13: `backlog-item-status.sh` — add `--tdd-report` and `--fix-commits`

**Files:**
- Create: `.claude/features/rabbit-backlog/test/test-tdd-report-backlog.sh`
- Modify: `.claude/features/rabbit-backlog/scripts/backlog-item-status.sh`

- [ ] **Step 1: Write the failing test**

```bash
#!/bin/bash
# test-tdd-report-backlog.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-backlog/scripts/backlog-item-status.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
ITEM_DIR="$TMPDIR_TEST/RABBIT-BACKLOG-99"
mkdir -p "$ITEM_DIR"

cat > "$ITEM_DIR/item.json" <<'JSON'
{"id":"RABBIT-BACKLOG-99","title":"test item","priority":"medium","status":"in-progress","history":[]}
JSON
cat > "$TMPDIR_TEST/tdd-report.json" <<'JSON'
{"schema_version":"1.0.0","feature":"test","test_result":"pass","tdd_state":"test-green",
 "impl_summary":"done","spec_compliance":"pass","test_gap_analysis":"none","impl_commit":"abc123"}
JSON

# 1. implemented with --tdd-report succeeds
bash "$SCRIPT" set "$ITEM_DIR" implemented \
  --reason "TDD complete" \
  --tdd-report "$TMPDIR_TEST/tdd-report.json" \
  --fix-commits "abc123" 2>/dev/null; code=$?
[ "$code" -eq 0 ] && ok "implemented with --tdd-report succeeds" || fail "implemented failed: $code"

# 2. item.json history has tdd_report field
has_rpt=$(python3 -c "
import json
h = json.load(open('$ITEM_DIR/item.json'))['history']
print('yes' if h and 'tdd_report' in h[-1] else 'no')
" 2>/dev/null)
[ "$has_rpt" = "yes" ] && ok "history has tdd_report field" || fail "missing tdd_report in history"

# 3. item.json history has fix_commits field
has_fc=$(python3 -c "
import json
h = json.load(open('$ITEM_DIR/item.json'))['history']
print('yes' if h and 'fix_commits' in h[-1] else 'no')
" 2>/dev/null)
[ "$has_fc" = "yes" ] && ok "history has fix_commits field" || fail "missing fix_commits in history"

# 4. status is now implemented
status=$(bash "$SCRIPT" get "$ITEM_DIR" 2>/dev/null)
[ "$status" = "implemented" ] && ok "status is implemented" || fail "status: got '$status'"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/rabbit-backlog/test/test-tdd-report-backlog.sh
```

- [ ] **Step 3: Update `backlog-item-status.sh`**

In the `set` subcommand, add flag parsing for the two new flags:

```bash
tdd_report_path=""
fix_commits=""
# In the flag-parsing loop, add:
--tdd-report)
  [ -z "${2:-}" ] && { echo "ERROR: --tdd-report requires a path" >&2; exit 2; }
  tdd_report_path="$2"; shift 2 ;;
--fix-commits)
  [ -z "${2:-}" ] && { echo "ERROR: --fix-commits requires a value" >&2; exit 2; }
  fix_commits="$2"; shift 2 ;;
```

When writing the `implemented` history entry, add the new fields:

```bash
# Read tdd_report JSON content
tdd_report_json="null"
if [ -n "$tdd_report_path" ] && [ -f "$tdd_report_path" ]; then
    tdd_report_json=$(cat "$tdd_report_path")
fi

# Use jq to write the updated item.json:
jq --arg new_status "implemented" \
   --arg reason "${reason:-}" \
   --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
   --arg fc "$fix_commits" \
   --argjson rpt "$tdd_report_json" \
   '.history += [{"status":"implemented","reason":$reason,"at":$ts,"fix_commits":$fc,"tdd_report":$rpt}] | .status = $new_status' \
   "$ITEM_DIR/item.json" > "$ITEM_DIR/item.json.tmp" \
   && mv "$ITEM_DIR/item.json.tmp" "$ITEM_DIR/item.json"
```

- [ ] **Step 4: Run all tests**

```bash
bash .claude/features/rabbit-backlog/test/test-tdd-report-backlog.sh
bash .claude/features/rabbit-backlog/test/run.sh
```

- [ ] **Step 5: Commit**

```bash
git add \
  .claude/features/rabbit-backlog/scripts/backlog-item-status.sh \
  .claude/features/rabbit-backlog/test/test-tdd-report-backlog.sh
git commit -m "feat(rabbit-backlog): add --tdd-report and --fix-commits to backlog-item-status.sh"
```

---

### Task 14: Revise `rabbit-bug` SKILL.md

**Files:**
- Modify: `.claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md`
- Modify: `.claude/skills/rabbit-bug/SKILL.md`

- [ ] **Step 1: Write test for SKILL.md content**

```bash
#!/bin/bash
# test-rabbit-bug-skill-v2.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL="$REPO_ROOT/.claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

[ -f "$SKILL" ] || { echo "FAIL: SKILL.md missing"; exit 1; }

for phrase in \
  "Filing protocol" \
  "Working protocol" \
  "eval subagent" \
  "rabbit-feature-touch" \
  "B/B mode" \
  "tdd-report.json" \
  "filing/RABBIT-BUG" \
  "auto-merge" \
  "status: success|failed" \
  "vet-triage.json"
do
  grep -qiE "$phrase" "$SKILL" \
    && ok "SKILL.md contains: $phrase" \
    || fail "SKILL.md missing: $phrase"
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/rabbit-bug/test/test-rabbit-bug-skill-v2.sh
```

- [ ] **Step 3: Rewrite `rabbit-bug` SKILL.md**

Replace the entire content:

````markdown
---
name: rabbit-bug
description: Use when Claude detects intent to file a bug, check bug status, list bugs, close/reopen/refuse a bug, or perform any bug lifecycle operation in this repository.
version: 2.0.0
owner: rabbit-bug
deprecation_criterion: when a unified tracking system replaces file-based bug management
---

## Overview

Two distinct protocols: **Filing** and **Working**. Scripts live at
`.claude/features/rabbit-bug/scripts/`. Bugs stored under `.claude/bugs/`.

---

## Filing Protocol

When the user confirms they want to file a bug:

1. Invoke `rabbit-feature-scope` to identify the related feature (or ask user if ambiguous).
2. Ask clarifying questions if bug description is insufficient for reproduction.
3. Run `file-bug.sh` to create the bug record and capture its directory path:
   ```bash
   BUG_DIR=$(bash .claude/features/rabbit-bug/scripts/file-bug.sh \
     --title "..." \
     --severity <low|medium|high|critical> \
     --description "..." \
     --related-feature <feature-name>)
   # BUG_DIR is e.g. .claude/bugs/rabbit-cage/RABBIT-BUG-5/
   BUG_ID=$(basename "$BUG_DIR")  # e.g. RABBIT-BUG-5
   ```
4. Create branch and commit:
   ```bash
   git checkout -b "filing/${BUG_ID}"
   git add "$BUG_DIR"
   git commit -m "filing: ${BUG_ID} — <title>"
   ```
5. Create **auto-merge PR** to main (metadata only, no code change).

---

## Working Protocol

When the user asks to work/fix a bug:

1. **Eval subagent** — dispatch a read-only default-model subagent:
   - Reads `bug.json` + current feature spec (`docs/spec/spec.md`)
   - Returns verdict: `valid` (bug still reproducible per spec) or `stale/invalid` with reason

2. **If stale/invalid:**
   - Confirm with user before proceeding.
   ```bash
   git checkout -b "filing/${BUG_ID}-invalidate"
   bash .claude/features/rabbit-bug/scripts/bug-status.sh set "$BUG_DIR" refused \
     --reason "<why it's invalid>"
   git add "$BUG_DIR/bug.json"
   git commit -m "refuse: ${BUG_ID} — <reason>"
   ```
   - Create **auto-merge PR** to main.

3. **If valid:**
   - Invoke `rabbit-feature-touch` in B/B mode, passing the bug dir.
     feature-touch reads `related_feature` from `bug.json` and creates the `fix/` branch.
   - Receive handoff: `{branch, tdd_report_path, status}`
   - **If `status: failed`:** surface error to user. Stop.
   - **If `status: success`:**
     ```bash
     # TDD_REPORT_PATH = handoff["tdd_report_path"] (set from feature-touch handoff above)
     bash .claude/features/rabbit-bug/scripts/bug-status.sh set "$BUG_DIR" closed \
       --reason "TDD cycle complete" \
       --tdd-report "$TDD_REPORT_PATH" \
       --fix-commits "$(python3 -c "import json; print(json.load(open('$TDD_REPORT_PATH'))['impl_commit'])")"
     git add "$BUG_DIR/bug.json"
     git commit -m "close: ${BUG_ID} — fix applied and verified"
     ```
   - Create **review PR** (same `fix/` branch — contains code fix + updated `bug.json`).

---

## Scripts Reference

| Script | Usage |
|---|---|
| `file-bug.sh` | `file-bug.sh --title T --severity S --description D [--related-feature F]` |
| `bug-status.sh get <dir>` | Print current status |
| `bug-status.sh set <dir> <status> --reason R [--tdd-report P] [--fix-commits C]` | Transition status |
| `list-bugs.sh [--status S] [--feature F] [--text]` | List bugs |

## Bug Close Requirements (R7)

Closing requires:
- `vet-triage.json` present in bug dir (run `rabbit-triage.sh` first, or use `--skip-vet-reason`)
- `--tdd-report <path>` flag provided to `bug-status.sh set closed`

## Status Lifecycle

```
open → closed | refused
closed → reopened
reopened → closed | refused
refused → reopened
```

## PR Tiers

| PR type | Branch | Merge |
|---|---|---|
| Filing | `filing/RABBIT-BUG-N` | Auto-merge |
| Refuse/invalidate | `filing/RABBIT-BUG-N-invalidate` | Auto-merge |
| Fix + close | `fix/<bug-id>-<keywords>` | Requires review |
````

- [ ] **Step 4: Copy to deployed location and run tests**

```bash
cp .claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md \
   .claude/skills/rabbit-bug/SKILL.md
bash .claude/features/rabbit-bug/test/test-rabbit-bug-skill-v2.sh
bash .claude/features/rabbit-bug/test/run.sh
```

- [ ] **Step 5: Commit**

```bash
git add \
  .claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md \
  .claude/skills/rabbit-bug/SKILL.md \
  .claude/features/rabbit-bug/test/test-rabbit-bug-skill-v2.sh
git commit -m "feat(rabbit-bug): revise SKILL.md — filing protocol, working protocol, B/B mode, R7 doc update"
```

---

### Task 15: Revise `rabbit-backlog` SKILL.md

**Files:**
- Modify: `.claude/features/rabbit-backlog/skills/rabbit-backlog/SKILL.md`
- Modify: `.claude/skills/rabbit-backlog/SKILL.md`

- [ ] **Step 1: Write test for SKILL.md content**

```bash
#!/bin/bash
# test-rabbit-backlog-skill-v2.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL="$REPO_ROOT/.claude/features/rabbit-backlog/skills/rabbit-backlog/SKILL.md"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

[ -f "$SKILL" ] || { echo "FAIL: SKILL.md missing"; exit 1; }

for phrase in \
  "Filing protocol" \
  "Working protocol" \
  "eval subagent" \
  "rabbit-feature-touch" \
  "B/B mode" \
  "tdd-report.json" \
  "filing/RABBIT-BACKLOG" \
  "auto-merge" \
  "status: success|failed" \
  "implemented"
do
  grep -qiE "$phrase" "$SKILL" \
    && ok "SKILL.md contains: $phrase" \
    || fail "SKILL.md missing: $phrase"
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

- [ ] **Step 2: Run to confirm it fails**

```bash
bash .claude/features/rabbit-backlog/test/test-rabbit-backlog-skill-v2.sh
```

- [ ] **Step 3: Rewrite `rabbit-backlog` SKILL.md**

Replace the entire content (mirrors rabbit-bug; vocabulary differences only):

````markdown
---
name: rabbit-backlog
description: Invoke when the user intends to file a backlog item, check backlog item status, transition a backlog item, or manage any backlog lifecycle in this repository.
version: 2.0.0
owner: rabbit-backlog
deprecation_criterion: when a unified tracking system replaces file-based backlog management
---

## Overview

Two distinct protocols: **Filing** and **Working**. Scripts live at
`.claude/features/rabbit-backlog/scripts/`. Items stored under `.claude/backlogs/`.

---

## Filing Protocol

When the user confirms they want to file a backlog item:

1. Invoke `rabbit-feature-scope` to identify the related feature (or ask user if ambiguous).
2. Ask clarifying questions if item description is unclear.
3. Run `file-backlog-item.sh` to create the item and capture its directory path:
   ```bash
   ITEM_DIR=$(bash .claude/features/rabbit-backlog/scripts/file-backlog-item.sh \
     --related-feature <feature-name> \
     --title "..." \
     [--priority <low|medium|high|critical>])
   # ITEM_DIR is e.g. .claude/backlogs/rabbit-cage/RABBIT-CAGE-BACKLOG-5/
   ITEM_ID=$(basename "$ITEM_DIR")
   ```
4. Create branch and commit:
   ```bash
   git checkout -b "filing/${ITEM_ID}"
   git add "$ITEM_DIR"
   git commit -m "filing: ${ITEM_ID} — <title>"
   ```
5. Create **auto-merge PR** to main (metadata only).

---

## Working Protocol

When the user asks to work a backlog item:

1. **Eval subagent** — dispatch a read-only default-model subagent:
   - Reads `item.json` + current feature spec (`docs/spec/spec.md`)
   - Returns verdict: `valid` (still relevant and correctly scoped) or `stale/invalid` with reason

2. **If stale/invalid:**
   - Confirm with user before proceeding.
   ```bash
   git checkout -b "filing/${ITEM_ID}-cancel"
   bash .claude/features/rabbit-backlog/scripts/backlog-item-status.sh set "$ITEM_DIR" cancelled \
     --reason "<why it's no longer relevant>"
   git add "$ITEM_DIR/item.json"
   git commit -m "cancel: ${ITEM_ID} — <reason>"
   ```
   - Create **auto-merge PR** to main.

3. **If valid:**
   - Invoke `rabbit-feature-touch` in B/B mode, passing the item dir.
     feature-touch reads `related_feature` from `item.json` and creates the `task/` branch.
   - Receive handoff: `{branch, tdd_report_path, status}`
   - **If `status: failed`:** surface error to user. Stop.
   - **If `status: success`:**
     ```bash
     # TDD_REPORT_PATH = handoff["tdd_report_path"] (set from feature-touch handoff above)
     bash .claude/features/rabbit-backlog/scripts/backlog-item-status.sh set "$ITEM_DIR" implemented \
       --reason "TDD cycle complete" \
       --tdd-report "$TDD_REPORT_PATH" \
       --fix-commits "$(python3 -c "import json; print(json.load(open('$TDD_REPORT_PATH'))['impl_commit'])")"
     git add "$ITEM_DIR/item.json"
     git commit -m "implement: ${ITEM_ID} — done"
     ```
   - Create **review PR** (same `task/` branch — contains implementation + updated `item.json`).

---

## Scripts Reference

| Script | Usage |
|---|---|
| `file-backlog-item.sh` | `file-backlog-item.sh --related-feature F --title T [--priority P]` |
| `backlog-item-status.sh get <dir>` | Print current status |
| `backlog-item-status.sh set <dir> <status> [--reason R] [--tdd-report P] [--fix-commits C]` | Transition |
| `list-backlog.sh [--status S] [--feature F] [--text]` | List items |

## Status Lifecycle

```
open → in-progress | cancelled
in-progress → implemented | cancelled
```

## PR Tiers

| PR type | Branch | Merge |
|---|---|---|
| Filing | `filing/RABBIT-BACKLOG-N` | Auto-merge |
| Cancel | `filing/RABBIT-BACKLOG-N-cancel` | Auto-merge |
| Implement + close | `task/<backlog-id>-<keywords>` | Requires review |
````

- [ ] **Step 4: Copy to deployed location and run tests**

```bash
cp .claude/features/rabbit-backlog/skills/rabbit-backlog/SKILL.md \
   .claude/skills/rabbit-backlog/SKILL.md
bash .claude/features/rabbit-backlog/test/test-rabbit-backlog-skill-v2.sh
bash .claude/features/rabbit-backlog/test/run.sh
```

- [ ] **Step 5: Commit**

```bash
git add \
  .claude/features/rabbit-backlog/skills/rabbit-backlog/SKILL.md \
  .claude/skills/rabbit-backlog/SKILL.md \
  .claude/features/rabbit-backlog/test/test-rabbit-backlog-skill-v2.sh
git commit -m "feat(rabbit-backlog): revise SKILL.md — filing protocol, working protocol, B/B mode"
```

---

## Final Verification

- [ ] **Run all feature test suites**

```bash
for f in .claude/features/*/test/run.sh; do
  echo "=== $(basename $(dirname $(dirname $f))) ==="
  bash "$f" || echo "FAILED: $f"
done
```

All must pass.

- [ ] **Smoke test `find-feature.sh`**

```bash
bash .claude/features/contract/scripts/find-feature.sh --list
bash .claude/features/contract/scripts/find-feature.sh contract
bash .claude/features/contract/scripts/find-feature.sh rabbit-feature-scope
```

Expected: `rabbit-feature-scope` is found and returns a path.

- [ ] **Verify `registry.json` is gone**

```bash
[ ! -f .claude/features/registry.json ] \
  && echo "PASS: registry.json removed" \
  || echo "FAIL: registry.json still exists"
```

- [ ] **Verify `CLAUDE.md` is pure pointer**

```bash
grep -vE '^(@|#|[[:space:]]*$)' CLAUDE.md \
  && echo "FAIL: CLAUDE.md has non-pointer content" \
  || echo "PASS: CLAUDE.md is pure pointer"
```

- [ ] **Verify `tdd-report.json` is gitignored**

```bash
touch tdd-report.json
git status --short tdd-report.json | grep -q '??' \
  && echo "PASS: tdd-report.json is gitignored" \
  || echo "FAIL: not gitignored"
rm tdd-report.json
```

- [ ] **Verify `rabbit-feature-scope` skill is deployed**

```bash
[ -f .claude/skills/rabbit-feature-scope/SKILL.md ] \
  && echo "PASS: skill deployed" \
  || echo "FAIL: skill not deployed"
```
