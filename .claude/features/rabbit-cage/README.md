# rabbit-workflow

Structured Claude Code workflow enforcing Machine First, Bounded Scope, and Designed Deprecation.

Policy is auto-injected every 20 prompts (configurable). Slash commands and skills included.

---

## Modes

Rabbit runs in two modes, detected automatically from the directory `claude` is launched from:

| Mode | Launch from | Who uses it |
|------|-------------|-------------|
| **Standalone** | repo root (`rabbit-workflow/`) | Developing rabbit itself |
| **Plugin** | `<your-project>/.rabbit/` | Applying rabbit to your project |

---

## Standalone mode (developing rabbit)

Clone the repo and launch `claude` from the root:

```bash
git clone https://github.com/changyu87/rabbit-workflow
cd rabbit-workflow
claude
```

Feature work lives in `.claude/features/`. The scope-guard enforces feature boundaries and the TDD subagent drives each feature through the full spec → test-red → impl → test-green cycle.

---

## Plugin mode (installing into your project)

Rabbit installs as a vendored `.rabbit/` directory committed to your project. No submodules; no external dependencies at runtime.

### Install

The one-liner fetches the latest release and runs `install.py --src ... --target .rabbit`:

```bash
cd /path/to/your/project
curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
```

The pipe to `bash` is explicit — this works from any shell including csh and tcsh.

If you prefer to download first:

```bash
curl -fsSLO https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh
bash install.sh      # must be bash — install.sh is not csh/tcsh compatible
```

Requires: `python3`, `curl`, `tar`.

### Commit the install

```bash
git add .rabbit/
git commit -m "install rabbit"
```

Collaborators get a complete rabbit install via `git clone` — no per-developer install step.

### Start a session

**bash / zsh:**
```bash
cd .rabbit/ && claude
```

**csh / tcsh:**
```tcsh
cd .rabbit/ && claude
```

The `&&` operator works in both. Once inside the Claude session, all hooks are Python — no further shell dependency.

### Declare a feature (map a code slice)

```bash
python3 .rabbit/.claude/features/rabbit-feature/scripts/scaffold-feature.py \
    my-feature ../src/auth/**
```

This scaffolds `.rabbit/rabbit-project/features/my-feature/` and registers the glob in `.rabbit/rabbit-project/project-map.json`. From then on, scope-guard blocks unsanctioned edits to `../src/auth/**`.

### Scope bypass (one-shot)

To make a single change without ceremony:

```bash
touch .rabbit/.runtime/scope-bypass-once
```

The marker is consumed on the next write — single-use only.

### Update

```bash
rm -rf .rabbit/
curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
git add .rabbit/
git commit -m "chore(rabbit): update to latest"
```

### Pin to a specific version

```bash
RABBIT_REF=v1.0.0 curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
```

`RABBIT_REF` accepts any branch, tag, or commit SHA. `RABBIT_REPO` overrides the default repo.

---

## Commands

| Command | Description |
|---|---|
| `/rabbit-refresh` | Re-inject policy into context |
| `/rabbit-config prompt-threshold N` | Set auto-refresh interval to N prompts |
| `/rabbit-config prompt-threshold` | Restore default (20 prompts) |
| `/rabbit-config allowed-tools add\|remove <tool>` | Manage Claude Code tool permissions |
| `/rabbit-config bash-allow add\|remove <cmd>` | Manage Bash command permissions |
| `/rabbit-config permissions lock\|unlock` | Lock/unlock write bit on protected dirs |
| `/rabbit-config human-approval true\|false` | Control Step 4 approval gate (true = gate active, false = bypass) |

---

## Uninstall

**Plugin mode:** `rm -rf .rabbit/` and remove `.rabbit` from `.gitignore` if present.

**Standalone mode:** delete the cloned repo.
