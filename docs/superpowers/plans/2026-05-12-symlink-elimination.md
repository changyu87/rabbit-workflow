# Symlink Elimination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **REQUIRED:** Every feature directory touch MUST use the rabbit-feature-touch skill (resolve scope → parallel TDD dispatch → verify HANDOFFs).

**Goal:** Replace all seven git-tracked symlinks with generated copies managed by a new unified `build.sh` + `build-contract.json` system.

**Architecture:** A machine-readable `build-contract.json` (owned by the `contract` feature) declares every generated artifact with its source, destination, type, and `check_on_stop` flag. A single `build.sh` (owned by `rabbit-cage`) reads it and builds everything. `test-generated-surface.sh` is the drift oracle — used by both the TDD test suite and the Stop hook.

**Tech Stack:** bash, python3 (json + shutil + subprocess), git

---

## File Map

**New files:**
- `.claude/features/contract/build-contract.json` — full target list (all generated artifacts)
- `.claude/features/contract/schemas/build-contract.schema.json` — JSON schema
- `.claude/features/rabbit-cage/scripts/build.sh` — unified builder, reads contract
- `.claude/features/rabbit-cage/test/test-generated-surface.sh` — drift oracle + TDD test

**Modified files:**
- `.claude/features/rabbit-cage/hooks/sync-check.sh` — replace three drift-check blocks with one `test-generated-surface.sh` / `build.sh` call
- `.claude/features/rabbit-cage/install.sh` — replace three generation calls with `build.sh TARGET`
- `.claude/features/rabbit-cage/feature.json` — retire `hooks`, `commands`, `settings` surface blocks; remove `generate-skills-dir.sh` from `scripts`, add `build.sh`
- `.claude/features/contract/feature.json` — retire `skills` surface block
- `.claude/features/rabbit-backlog/feature.json` — retire `skills` surface block
- `.claude/features/rabbit-bug/feature.json` — retire `skills` surface block
- `.claude/features/tdd-state-machine/feature.json` — retire `skills` surface block

**Deleted files:**
- `.claude/features/contract/scripts/relink.sh`
- `.claude/features/rabbit-cage/scripts/generate-skills-dir.sh`
- `.claude/features/rabbit-cage/test/test-symlinks.sh`

---

## Task 1: Scope Resolution

- [ ] **Step 1: Run resolve-feature-scope.sh via Opus**

```bash
SCOPE_PROMPT=$(bash .claude/features/tdd-state-machine/scripts/resolve-feature-scope.sh \
  "Symlink elimination: add build-contract.json and schema to contract feature; add build.sh, test-generated-surface.sh to rabbit-cage; update sync-check.sh, install.sh, feature.json in rabbit-cage; delete relink.sh from contract; delete generate-skills-dir.sh and test-symlinks.sh from rabbit-cage; retire surface.skills in rabbit-backlog, rabbit-bug, tdd-state-machine, and contract features.")
```

Then dispatch Agent with `model: opus` and `prompt: $SCOPE_PROMPT`.

Expected response JSON:
```json
{"features": ["contract", "rabbit-cage", "rabbit-backlog", "rabbit-bug", "tdd-state-machine"], "rationale": "..."}
```

---

## Task 2: TDD — contract feature

**Dependency:** none. Run before Task 3 (rabbit-cage needs build-contract.json to exist).

- [ ] **Step 1: Dispatch contract feature TDD**

```bash
PROMPT=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh contract \
  "Create build-contract.json and its schema. Retire surface.skills in feature.json. Delete relink.sh.")
# Dispatch Agent(prompt: PROMPT)
```

The subagent must implement:

**`.claude/features/contract/build-contract.json`** (full content):
```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively manages workspace artifact generation",
  "updated": "2026-05-12",
  "targets": [
    {
      "name": "CLAUDE.md",
      "type": "generate-claude-md",
      "destination": "CLAUDE.md",
      "check_on_stop": true
    },
    {
      "name": "hooks/refresh.sh",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/hooks/refresh.sh",
      "destination": ".claude/hooks/refresh.sh",
      "check_on_stop": true
    },
    {
      "name": "hooks/scope-guard.sh",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/hooks/scope-guard.sh",
      "destination": ".claude/hooks/scope-guard.sh",
      "check_on_stop": true
    },
    {
      "name": "hooks/session-init.sh",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/hooks/session-init.sh",
      "destination": ".claude/hooks/session-init.sh",
      "check_on_stop": true
    },
    {
      "name": "hooks/sync-check.sh",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/hooks/sync-check.sh",
      "destination": ".claude/hooks/sync-check.sh",
      "check_on_stop": true
    },
    {
      "name": "commands/rabbit-refresh.md",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/commands/rabbit-refresh.md",
      "destination": ".claude/commands/rabbit-refresh.md",
      "check_on_stop": true
    },
    {
      "name": "commands/rabbit-set-threshold.md",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/commands/rabbit-set-threshold.md",
      "destination": ".claude/commands/rabbit-set-threshold.md",
      "check_on_stop": true
    },
    {
      "name": "commands/rabbit-project.md",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/commands/rabbit-project.md",
      "destination": ".claude/commands/rabbit-project.md",
      "check_on_stop": true
    },
    {
      "name": "settings.json",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/settings.json",
      "destination": ".claude/settings.json",
      "check_on_stop": true
    },
    {
      "name": "skills/rabbit-backlog/SKILL.md",
      "type": "copy-file",
      "source": ".claude/features/rabbit-backlog/skills/rabbit-backlog/SKILL.md",
      "destination": ".claude/skills/rabbit-backlog/SKILL.md",
      "check_on_stop": true
    },
    {
      "name": "skills/rabbit-bug/SKILL.md",
      "type": "copy-file",
      "source": ".claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md",
      "destination": ".claude/skills/rabbit-bug/SKILL.md",
      "check_on_stop": true
    },
    {
      "name": "skills/rabbit-feature-touch/SKILL.md",
      "type": "copy-file",
      "source": ".claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md",
      "destination": ".claude/skills/rabbit-feature-touch/SKILL.md",
      "check_on_stop": true
    },
    {
      "name": "skills/rabbit-workspace-map/SKILL.md",
      "type": "copy-file",
      "source": ".claude/features/contract/skills/rabbit-workspace-map/SKILL.md",
      "destination": ".claude/skills/rabbit-workspace-map/SKILL.md",
      "check_on_stop": true
    },
    {
      "name": "README.md",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/README.md",
      "destination": "README.md",
      "check_on_stop": false
    },
    {
      "name": "install.sh",
      "type": "copy-file",
      "source": ".claude/features/rabbit-cage/install.sh",
      "destination": "install.sh",
      "check_on_stop": false
    }
  ]
}
```

**`.claude/features/contract/schemas/build-contract.schema.json`**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "build-contract",
  "type": "object",
  "required": ["schema_version", "owner", "targets"],
  "properties": {
    "schema_version": {"type": "string"},
    "owner": {"type": "string"},
    "deprecation_criterion": {"type": "string"},
    "updated": {"type": "string"},
    "targets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type", "destination", "check_on_stop"],
        "properties": {
          "name": {"type": "string"},
          "type": {"type": "string", "enum": ["copy-file", "generate-claude-md"]},
          "source": {"type": "string"},
          "destination": {"type": "string"},
          "check_on_stop": {"type": "boolean"}
        },
        "if": {"properties": {"type": {"const": "copy-file"}}},
        "then": {"required": ["source"]}
      }
    }
  }
}
```

**`contract/feature.json` surface changes:** set `skills: []`.

**Delete:** `.claude/features/contract/scripts/relink.sh`

The TDD test for this feature should:
- Validate `build-contract.json` against its schema using `jsonschema` or manual checks
- Verify all declared `source` paths exist
- Verify `relink.sh` does not exist

- [ ] **Step 2: Verify HANDOFF shows tdd_state: test-green**

---

## Task 3: TDD — rabbit-cage feature

**Dependency:** Task 2 must be complete (build-contract.json must exist).

- [ ] **Step 1: Dispatch rabbit-cage feature TDD**

```bash
PROMPT=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh rabbit-cage \
  "Create build.sh and test-generated-surface.sh. Update sync-check.sh, install.sh, feature.json. Delete generate-skills-dir.sh and test-symlinks.sh.")
# Dispatch Agent(prompt: PROMPT)
```

The subagent must implement:

**`.claude/features/rabbit-cage/scripts/build.sh`**:
```bash
#!/usr/bin/env bash
# build.sh — unified workspace artifact builder.
#
# Reads .claude/features/contract/build-contract.json and builds all declared targets.
# Usage: build.sh [REPO_ROOT]
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively manages workspace artifact generation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
CONTRACT="$REPO_ROOT/.claude/features/contract/build-contract.json"
GENERATE_CLAUDE_MD="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

[ -f "$CONTRACT" ] || { echo "build: contract not found: $CONTRACT" >&2; exit 1; }

python3 - "$REPO_ROOT" "$CONTRACT" "$GENERATE_CLAUDE_MD" <<'PYEOF'
import json, os, shutil, subprocess, sys

repo_root, contract_path, generate_script = sys.argv[1], sys.argv[2], sys.argv[3]

with open(contract_path) as f:
    contract = json.load(f)

errors = 0
for target in contract.get("targets", []):
    name = target["name"]
    ttype = target["type"]
    destination = os.path.join(repo_root, target["destination"])

    if ttype == "generate-claude-md":
        result = subprocess.run(
            ["bash", generate_script, "--write", repo_root],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  [error] {name}: generate-claude-md failed\n{result.stderr}", file=sys.stderr)
            errors += 1
        else:
            print(f"  [built] {name}")

    elif ttype == "copy-file":
        source = os.path.join(repo_root, target["source"])
        if not os.path.isfile(source):
            print(f"  [error] build: source not found: {target['source']}", file=sys.stderr)
            errors += 1
            continue
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        print(f"  [built] {name}")

    else:
        print(f"  [error] unknown type '{ttype}' for target '{name}'", file=sys.stderr)
        errors += 1

if errors:
    print(f"\nbuild: {errors} error(s)", file=sys.stderr)
    sys.exit(1)
PYEOF
```

**`.claude/features/rabbit-cage/test/test-generated-surface.sh`** (replaces test-symlinks.sh):
```bash
#!/usr/bin/env bash
# test-generated-surface.sh — drift oracle for workspace-generated artifacts.
#
# Reads build-contract.json. Verifies build.sh exists, then diffs each
# check_on_stop:true copy-file target against its source.
# Exits 0 (all pass) or 1 (any fail).
#
# Used by: sync-check.sh (Stop hook) + TDD test suite.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively manages workspace artifact generation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CONTRACT="$REPO_ROOT/.claude/features/contract/build-contract.json"
BUILD_SH="$REPO_ROOT/.claude/features/rabbit-cage/scripts/build.sh"

pass=0
fail=0

ok()     { echo "  PASS t$1: $2"; pass=$((pass+1)); }
fail_t() { echo "  FAIL t$1: $2"; fail=$((fail+1)); }

echo "test-generated-surface.sh"

# t1: build.sh exists and is executable
if [ -x "$BUILD_SH" ]; then
    ok 1 "build.sh exists and is executable"
else
    fail_t 1 "build.sh not found or not executable at $BUILD_SH"
fi

# t2: build-contract.json exists
if [ -f "$CONTRACT" ]; then
    ok 2 "build-contract.json exists"
else
    fail_t 2 "build-contract.json not found at $CONTRACT"
fi

if [ "$fail" -gt 0 ]; then
    echo ""
    echo "Results: $pass passed, $fail failed"
    exit 1
fi

# t3+: each check_on_stop:true copy-file target matches its source
t=3
while IFS=$'\t' read -r name source destination; do
    src_abs="$REPO_ROOT/$source"
    dst_abs="$REPO_ROOT/$destination"
    if [ ! -f "$dst_abs" ]; then
        fail_t $t "$name: destination missing ($destination)"
    elif diff -q "$src_abs" "$dst_abs" >/dev/null 2>&1; then
        ok $t "$name: matches source"
    else
        fail_t $t "$name: drifted from source"
    fi
    t=$((t+1))
done < <(python3 -c "
import json
with open('$CONTRACT') as f:
    c = json.load(f)
for t in c['targets']:
    if t.get('check_on_stop') and t['type'] == 'copy-file':
        print(t['name'] + '\t' + t['source'] + '\t' + t['destination'])
")

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
```

**`sync-check.sh` change** — replace the entire skills drift block (from `# Skills drift check` comment through the closing `fi`) with:
```bash
# Surface drift check — only reached when CLAUDE.md is clean (no double JSON output).
_TEST_SURFACE="$REPO_ROOT/.claude/features/rabbit-cage/test/test-generated-surface.sh"
_BUILD="$REPO_ROOT/.claude/features/rabbit-cage/scripts/build.sh"
if [ -f "$_TEST_SURFACE" ] && ! bash "$_TEST_SURFACE" >/dev/null 2>&1; then
  bash "$_BUILD" "$REPO_ROOT" >/dev/null 2>&1 || true
  python3 -c "
import json
print(json.dumps({
    'systemMessage': '\x1b[32m🔄 ━━━ [rabbit] Surface drift detected — workspace rebuilt from sources ━━━ 🔄\x1b[0m'
}))
"
fi
```

**`install.sh` change** — replace these three lines:
```bash
bash "$TARGET/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" --write "$TARGET"
...
bash "$TARGET/.claude/features/contract/scripts/relink.sh" "$TARGET/.claude/features" "$TARGET"

# Generate .claude/skills/ from feature surface declarations.
bash "$TARGET/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh" "$TARGET"
```
with:
```bash
bash "$TARGET/.claude/features/rabbit-cage/scripts/build.sh" "$TARGET"
```

**`rabbit-cage/feature.json` surface changes:**
- Set `hooks: []`, `commands: []`, `settings: []`
- In `scripts`: remove `generate-skills-dir.sh`, add `.claude/features/rabbit-cage/scripts/build.sh`

**Delete:**
- `.claude/features/rabbit-cage/scripts/generate-skills-dir.sh`
- `.claude/features/rabbit-cage/test/test-symlinks.sh`

The TDD test at test-red is `test-generated-surface.sh` failing on t1 (build.sh not found). At test-green, all tests pass.

- [ ] **Step 2: Verify HANDOFF shows tdd_state: test-green**

---

## Task 4: TDD — retire surface.skills (parallel)

**Dependency:** Tasks 2 and 3 complete.

These three features only need their `feature.json` `skills` surface block set to `[]`. Dispatch in parallel.

- [ ] **Step 1: Dispatch all three in parallel**

```bash
PROMPT_RB=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh rabbit-backlog \
  "Retire surface.skills in feature.json: set skills to empty array [].")
PROMPT_BUG=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh rabbit-bug \
  "Retire surface.skills in feature.json: set skills to empty array [].")
PROMPT_TDD=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh tdd-state-machine \
  "Retire surface.skills in feature.json: set skills to empty array [].")
# Dispatch all three Agent() calls simultaneously
```

Each subagent:
1. Opens `feature.json`, sets `surface.skills` to `[]`
2. Writes a test asserting `surface.skills` is empty
3. Commits

- [ ] **Step 2: Verify all three HANDOFFs show tdd_state: test-green**

---

## Task 5: Git symlink migration

**Dependency:** Tasks 2, 3, and 4 complete. `build.sh` must exist.

- [ ] **Step 1: Remove all symlinks from git**

```bash
git rm .claude/commands .claude/contract .claude/hooks .claude/policy .claude/settings.json README.md install.sh
```

Expected: git removes symlink entries from index; filesystem symlinks gone.

- [ ] **Step 2: Run build.sh to produce real files**

```bash
bash .claude/features/rabbit-cage/scripts/build.sh
```

Expected output: lines like `  [built] hooks/refresh.sh`, one per target.

- [ ] **Step 3: Verify no symlinks remain**

```bash
git ls-files -s | awk '$1 ~ /^12/' | awk '{print $4}'
```

Expected: empty output.

- [ ] **Step 4: Stage and commit real files**

```bash
git add .claude/hooks/ .claude/commands/ .claude/settings.json \
        .claude/skills/ CLAUDE.md README.md install.sh
git commit -m "$(cat <<'EOF'
chore(rabbit-cage): replace git-tracked symlinks with generated copies

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Verification

- [ ] **Step 1: Run test-generated-surface.sh**

```bash
bash .claude/features/rabbit-cage/test/test-generated-surface.sh
```

Expected: all tests pass, 0 failed.

- [ ] **Step 2: Confirm no git-tracked symlinks**

```bash
git ls-files -s | awk '$1 ~ /^12/' | awk '{print $4}'
```

Expected: empty.

- [ ] **Step 3: Smoke-test install.sh in a temp dir**

```bash
TMP=$(mktemp -d)
bash install.sh "$TMP"
ls "$TMP/.claude/hooks/" "$TMP/.claude/commands/" "$TMP/.claude/settings.json" "$TMP/CLAUDE.md"
rm -rf "$TMP"
```

Expected: all paths exist as regular files.

---

After committing, run the validate-all suite:

```bash
bash .claude/features/contract/scripts/validate-all.sh 2>/dev/null || \
bash .claude/features/rabbit-cage/scripts/validate-all.sh 2>/dev/null
```

---

Then commit the plan file:
```
git add docs/superpowers/plans/2026-05-12-symlink-elimination.md
git commit -m "$(cat <<'EOF'
docs: add symlink elimination implementation plan

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```
