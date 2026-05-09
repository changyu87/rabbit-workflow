# Install Script, Test Suite & README — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `install.sh`, an automated E2E test suite, and `README.md` to the `rwf-features-and-hierarchy` branch.

**Architecture:** `install.sh` is a dual-mode bash script (local-copy when `.claude/` is next to it; GitHub tarball download otherwise). `test/test-install.sh` runs 9 isolated sandbox tests with no external dependencies. `README.md` documents both developer and user install paths.

**Tech Stack:** bash, python3 (stdlib only — json, os, pathlib, sys), git, curl, tar

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `install.sh` | Create | Copy `.claude/` + `CLAUDE.md` to TARGET; dual-mode source detection; fail-safe |
| `test/test-install.sh` | Create | 9-case E2E test suite; each test in isolated `mktemp -d` sandbox |
| `README.md` | Create | User-facing docs: what it is, developer install, user install, commands |

---

## Task 1: Write the test suite

**Files:**
- Create: `test/test-install.sh`

Context: Write all 9 tests first. They will all fail because `install.sh` does not exist yet. That is the expected state after this task.

The hook (`rwf-refresh.sh`) increments the counter, then emits JSON only when `count >= THRESHOLD`. To trigger JSON output in test 7: seed the counter file at `THRESHOLD - 1` (= 19 when `RWF_REFRESH_EVERY=20`), so after the hook increments it reaches 20, which is not less than 20.

The threshold command Python block is extracted from the installed `.md` file via `sed` so the test exercises the real shipped code.

- [ ] **Step 1: Create `test/` directory and write `test/test-install.sh`**

```bash
mkdir -p test
```

Content of `test/test-install.sh`:

```bash
#!/usr/bin/env bash
# E2E tests for install.sh. Run: bash test/test-install.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"

PASS=0
FAIL=0

run() {
    local name="$1"
    shift
    local dir
    dir="$(mktemp -d)"
    if (export DIR="$dir"; "$@") 2>/dev/null; then
        printf "PASS: %s\n" "$name"
        PASS=$((PASS + 1))
    else
        printf "FAIL: %s\n" "$name"
        FAIL=$((FAIL + 1))
    fi
    rm -rf "$dir"
}

# ── test functions ────────────────────────────────────────────────────────────

t1_clean_install() {
    "$INSTALL" "$DIR" >/dev/null
    [[ -d "$DIR/.claude" && -f "$DIR/CLAUDE.md" ]]
}

t2_hook_executable() {
    "$INSTALL" "$DIR" >/dev/null
    [[ -x "$DIR/.claude/hooks/rwf-refresh.sh" ]]
}

t3_settings_content() {
    "$INSTALL" "$DIR" >/dev/null
    python3 -c "
import json
data = json.load(open('$DIR/.claude/settings.json'))
assert data['env']['RWF_REFRESH_EVERY'] == '20', repr(data)
"
}

t4_claude_imports() {
    "$INSTALL" "$DIR" >/dev/null
    grep -q '@./.claude/philosophy.md' "$DIR/CLAUDE.md" &&
    grep -q '@./.claude/work-guide.md' "$DIR/CLAUDE.md"
}

t5_existing_claude_blocked() {
    mkdir "$DIR/.claude"
    ! "$INSTALL" "$DIR" >/dev/null
}

t6_no_arg_installs_to_pwd() {
    (cd "$DIR" && "$INSTALL" >/dev/null)
    [[ -d "$DIR/.claude" && -f "$DIR/CLAUDE.md" ]]
}

t7_hook_json_output() {
    "$INSTALL" "$DIR" >/dev/null
    # Seed counter at THRESHOLD-1 so next increment hits threshold
    echo 19 >"$DIR/.rwf-prompt-counter"
    local out
    out="$(mktemp)"
    (cd "$DIR" && RWF_REFRESH_EVERY=20 .claude/hooks/rwf-refresh.sh >"$out")
    python3 - "$out" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
assert 'additionalContext' in data, f"missing additionalContext; got: {data}"
EOF
    rm -f "$out"
}

t8a_threshold_invalid_rejected() {
    "$INSTALL" "$DIR" >/dev/null
    local pyblock
    pyblock=$(sed -n '/python3 -c "/,/^"`$/{/python3 -c "/d; /^"`$/d; p}' \
        "$DIR/.claude/commands/rwf-set-threshold.md")
    ! (cd "$DIR" && THRESHOLD="abc" python3 -c "$pyblock")
}

t8b_threshold_valid_writes_json() {
    "$INSTALL" "$DIR" >/dev/null
    local pyblock
    pyblock=$(sed -n '/python3 -c "/,/^"`$/{/python3 -c "/d; /^"`$/d; p}' \
        "$DIR/.claude/commands/rwf-set-threshold.md")
    (cd "$DIR" && THRESHOLD="15" python3 -c "$pyblock" >/dev/null)
    python3 -c "
import json
data = json.load(open('$DIR/.claude/settings.local.json'))
assert data['env']['RWF_REFRESH_EVERY'] == '15', repr(data)
"
}

# ── run all ───────────────────────────────────────────────────────────────────

run "1: clean install — files present"          t1_clean_install
run "2: hook is executable"                     t2_hook_executable
run "3: settings.json has RWF_REFRESH_EVERY=20" t3_settings_content
run "4: CLAUDE.md imports .claude files"        t4_claude_imports
run "5: existing .claude/ blocks install"       t5_existing_claude_blocked
run "6: no arg installs to \$PWD"               t6_no_arg_installs_to_pwd
run "7: hook emits valid JSON at threshold"     t7_hook_json_output
run "8a: threshold rejects invalid arg"         t8a_threshold_invalid_rejected
run "8b: threshold writes correct JSON"         t8b_threshold_valid_writes_json

echo ""
printf "%d passed, %d failed\n" "$PASS" "$FAIL"
[[ $FAIL -eq 0 ]]
```

- [ ] **Step 2: Make the test file executable**

```bash
chmod +x test/test-install.sh
```

- [ ] **Step 3: Run the test suite — verify all 9 fail**

```bash
bash test/test-install.sh
```

Expected output (exact counts matter; all must be FAIL):

```
FAIL: 1: clean install — files present
FAIL: 2: hook is executable
FAIL: 3: settings.json has RWF_REFRESH_EVERY=20
FAIL: 4: CLAUDE.md imports .claude files
FAIL: 5: existing .claude/ blocks install
FAIL: 6: no arg installs to $PWD
FAIL: 7: hook emits valid JSON at threshold
FAIL: 8a: threshold rejects invalid arg
FAIL: 8b: threshold writes correct JSON

0 passed, 9 failed
```

Exit code: 1. If any test passes at this point, something is wrong — investigate before continuing.

- [ ] **Step 4: Commit the test file**

```bash
git add test/test-install.sh
git commit -m "Add E2E test suite for install script (all failing — TDD)"
```

---

## Task 2: Implement `install.sh`

**Files:**
- Create: `install.sh`

Context: `install.sh` must satisfy all 9 tests. Key behaviors:
- `TARGET` defaults to `$PWD` when no argument given (satisfies test 6)
- Fail-safe: abort if `TARGET/.claude` exists (test 5)
- Source detection: if `SCRIPT_DIR/.claude` exists → local copy; otherwise → download from GitHub (tests 1–4, 6, 7, 8 all use local mode since `$INSTALL` points into the repo)
- `chmod +x` on `rwf-refresh.sh` after copy (test 2)
- The `|| echo ""` fallback ensures `SCRIPT_DIR` is empty (not an error) in curl-pipe mode where `BASH_SOURCE[0]` is `/dev/stdin`; the `[[ -n "$SCRIPT_DIR" && ...]]` guard prevents a false match

- [ ] **Step 1: Write `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-$PWD}"

if [[ -d "$TARGET/.claude" ]]; then
    echo "Error: $TARGET/.claude already exists." >&2
    echo "If developing rabbit-workflow, no install needed — open this directory in Claude Code." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.claude" ]]; then
    cp -r "$SCRIPT_DIR/.claude" "$TARGET/.claude"
    cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"
else
    TMP="$(mktemp -d)"
    trap "rm -rf '$TMP'" EXIT
    curl -fsSL https://github.com/USER/rabbit-workflow/archive/refs/heads/main.tar.gz \
        | tar -xz -C "$TMP" --strip-components=1
    cp -r "$TMP/.claude" "$TARGET/.claude"
    cp "$TMP/CLAUDE.md" "$TARGET/CLAUDE.md"
fi

chmod +x "$TARGET/.claude/hooks/rwf-refresh.sh"
echo "rabbit-workflow installed to $TARGET"
```

- [ ] **Step 2: Make `install.sh` executable**

```bash
chmod +x install.sh
```

- [ ] **Step 3: Run the test suite — verify all 9 pass**

```bash
bash test/test-install.sh
```

Expected:

```
PASS: 1: clean install — files present
PASS: 2: hook is executable
PASS: 3: settings.json has RWF_REFRESH_EVERY=20
PASS: 4: CLAUDE.md imports .claude files
PASS: 5: existing .claude/ blocks install
PASS: 6: no arg installs to $PWD
PASS: 7: hook emits valid JSON at threshold
PASS: 8a: threshold rejects invalid arg
PASS: 8b: threshold writes correct JSON

9 passed, 0 failed
```

Exit code: 0. If any test fails, fix `install.sh` before committing. Do not proceed to Task 3 with failing tests.

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "Add install.sh with local and download modes, fail-safe on existing .claude/"
```

---

## Task 3: Write `README.md`

**Files:**
- Create: `README.md`

Context: `USER` is a placeholder for the GitHub username — leave it as-is. It will be replaced when the repo is published (tracked in the spec's Known Placeholders section).

- [ ] **Step 1: Write `README.md`**

~~~markdown
# rabbit-workflow

Structured Claude Code workflow enforcing Machine First, Bounded Scope, and Designed Deprecation.

Policy is auto-injected every 20 prompts (configurable). Two slash commands included.

---

## For developers (contributing to rabbit-workflow)

**git**
```bash
git clone https://github.com/USER/rabbit-workflow
git clone https://github.com/USER/rabbit-workflow my-name  # custom workspace name
```

**curl** (installs to current directory)
```bash
mkdir my-rabbit && cd my-rabbit
bash <(curl -fsSL https://raw.githubusercontent.com/USER/rabbit-workflow/main/install.sh)
```

---

## For users (installing into your own workspace)

Your target workspace must not have an existing `.claude/` directory.

**git**
```bash
git clone https://github.com/USER/rabbit-workflow
./rabbit-workflow/install.sh /path/to/your/workspace   # explicit target
./rabbit-workflow/install.sh                           # or install to $PWD
```

**curl** (installs to current directory)
```bash
cd /path/to/your/workspace
bash <(curl -fsSL https://raw.githubusercontent.com/USER/rabbit-workflow/main/install.sh)
```

---

## Commands

| Command | Description |
|---|---|
| `/rwf-refresh` | Manually re-inject policy |
| `/rwf-set-threshold N` | Set auto-refresh interval (takes effect next session) |

## Configuration

Default refresh interval: 20 prompts. Change with `/rwf-set-threshold N`.

## Uninstall

Remove `.claude/` and `CLAUDE.md` from the installed workspace.
~~~

- [ ] **Step 2: Run the test suite one final time to confirm nothing regressed**

```bash
bash test/test-install.sh
```

Expected: `9 passed, 0 failed` with exit code 0.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Add README with developer and user install instructions"
```

---

## Acceptance Checklist

After all three tasks:

- [ ] `bash test/test-install.sh` exits 0, prints `9 passed, 0 failed`
- [ ] `./install.sh /tmp/fresh-test && ls /tmp/fresh-test` shows `.claude/` and `CLAUDE.md`
- [ ] `./install.sh /tmp/fresh-test` a second time exits 1 with "already exists" message
- [ ] `README.md` exists at repo root
- [ ] `git status` is clean
