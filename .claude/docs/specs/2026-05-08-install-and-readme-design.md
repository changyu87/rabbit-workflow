# Install Script & README — Design

**Date:** 2026-05-08
**Status:** Ready for implementation
**Owner:** rabbit-workflow team
**Deprecation criterion:** Superseded when install mechanism changes (e.g., package manager, submodule)

---

## 1. Motivation

rabbit-workflow needs two things to be usable by others:

1. **An install script** — copies `.claude/` and `CLAUDE.md` into a user's workspace with a fail-safe against overwriting an existing workflow
2. **A README** — documents how to install for both developers and users, with both git and curl paths

---

## 2. Decisions

### 2.1 Install target default

`./install.sh` with no argument installs to `$PWD`. An explicit path overrides:

```bash
./install.sh                        # installs to current directory
./install.sh /path/to/workspace     # installs to explicit target
```

### 2.2 Fail-safe

If `TARGET/.claude` already exists, the script prints a clear error and exits 1. No partial copies. The error message distinguishes the developer case (no install needed) from a real collision.

### 2.3 Dual-mode source detection

The script detects how it was invoked:

- **Local mode** — `SCRIPT_DIR/.claude` exists → copy from there (git clone case)
- **Download mode** — no local `.claude/` → fetch tarball from GitHub, extract to `mktemp -d`, copy, clean up (curl-pipe-bash case)

This makes one script serve both invocation styles without user intervention.

### 2.4 Curl invocation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/USER/rabbit-workflow/main/install.sh)
```

When piped through bash, `BASH_SOURCE[0]` does not resolve to a directory containing `.claude/`, so download mode activates automatically.

### 2.5 What gets installed

| Artifact | Installed |
|---|---|
| `.claude/` | yes |
| `CLAUDE.md` | yes |
| `install.sh` | no |
| `test/` | no |
| `README.md` | no |
| `archive/` | no |
| `.gitignore` | no |

### 2.6 Testing

Fully automated bash test suite in `test/test-install.sh`. No external dependencies. Each case runs in an isolated `mktemp -d` sandbox cleaned up on exit. Covers install success, file presence, permissions, content correctness, and all fail-safe conditions.

---

## 3. New Files

```
rabbit-workflow/
├── install.sh              ← NEW
├── test/
│   └── test-install.sh     ← NEW
└── README.md               ← NEW
```

---

## 4. File Specifications

### 4.1 `install.sh`

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
if [[ -d "$SCRIPT_DIR/.claude" ]]; then
    cp -r "$SCRIPT_DIR/.claude" "$TARGET/.claude"
    cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"
else
    TMP="$(mktemp -d)"
    trap "rm -rf $TMP" EXIT
    curl -fsSL https://github.com/USER/rabbit-workflow/archive/refs/heads/main.tar.gz \
        | tar -xz -C "$TMP" --strip-components=1
    cp -r "$TMP/.claude" "$TARGET/.claude"
    cp "$TMP/CLAUDE.md" "$TARGET/CLAUDE.md"
fi

chmod +x "$TARGET/.claude/hooks/rwf-refresh.sh"
echo "rabbit-workflow installed to $TARGET"
```

### 4.2 `test/test-install.sh` — 8 test cases

| # | Case | Expected |
|---|---|---|
| 1 | Clean install (local mode) | exit 0, `.claude/` and `CLAUDE.md` present |
| 2 | `rwf-refresh.sh` permissions | executable after install |
| 3 | `settings.json` content | contains `RWF_REFRESH_EVERY` = `"20"` |
| 4 | `CLAUDE.md` imports | references `.claude/philosophy.md` and `.claude/work-guide.md` |
| 5 | Existing `TARGET/.claude` | exit 1 |
| 6 | No argument | installs to `$PWD`, exit 0 in fresh dir |
| 7 | `rwf-refresh.sh` invoked directly | produces valid JSON |
| 8 | Threshold command | invalid arg → exit 1; valid arg → correct JSON in `settings.local.json` |

### 4.3 `README.md`

```markdown
# rabbit-workflow

Structured Claude Code workflow enforcing Machine First, Bounded Scope, and Designed Deprecation.

Policy is auto-injected every 20 prompts (configurable). Two slash commands included.

## For developers (contributing to rabbit-workflow)

**git**
\`\`\`bash
git clone https://github.com/USER/rabbit-workflow
git clone https://github.com/USER/rabbit-workflow my-name  # custom workspace name
\`\`\`

**curl** (installs to current directory)
\`\`\`bash
mkdir my-rabbit && cd my-rabbit
bash <(curl -fsSL https://raw.githubusercontent.com/USER/rabbit-workflow/main/install.sh)
\`\`\`

## For users (installing into your own workspace)

**git**
\`\`\`bash
git clone https://github.com/USER/rabbit-workflow
./rabbit-workflow/install.sh /path/to/your/workspace   # explicit target
./rabbit-workflow/install.sh                           # or install to $PWD
\`\`\`

**curl** (installs to current directory)
\`\`\`bash
cd /path/to/your/workspace
bash <(curl -fsSL https://raw.githubusercontent.com/USER/rabbit-workflow/main/install.sh)
\`\`\`

## Commands

| Command | Description |
|---|---|
| `/rwf-refresh` | Manually re-inject policy |
| `/rwf-set-threshold N` | Set auto-refresh interval (takes effect next session) |

## Configuration

Default refresh interval: 20 prompts. Change with `/rwf-set-threshold N`.

## Uninstall

Remove `.claude/` and `CLAUDE.md` from the installed workspace.
```

---

## 5. Out of Scope

- Package manager distribution (brew, npm, etc.)
- Windows support
- Upgrade path (installing over an older version)
- Testing the curl/download mode in CI (requires published repo)

---

## 6. Acceptance Criteria

- `./install.sh ~/fresh-workspace` copies `.claude/` and `CLAUDE.md`, exits 0
- `./install.sh` with no argument installs to `$PWD`, exits 0 in fresh directory
- `./install.sh TARGET` where `TARGET/.claude` exists exits 1 with descriptive message
- `rwf-refresh.sh` is executable in installed workspace
- `bash test/test-install.sh` exits 0 with all 8 cases passing
- `README.md` exists at repo root with both git and curl paths for both roles
