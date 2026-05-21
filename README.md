# rabbit-workflow

Structured Claude Code workflow enforcing Machine First, Bounded Scope, and Designed Deprecation.

Policy is auto-injected every 20 prompts (configurable). Slash commands and skills included.

---

## For developers (contributing to rabbit-workflow)

**git**
```bash
git clone https://github.com/USER/rabbit-workflow
git clone https://github.com/USER/rabbit-workflow my-name  # custom workspace name
```

---

## For users (installing into your own workspace)

Your target workspace must not have an existing `.claude/` directory.

**git**
```bash
git clone https://github.com/USER/rabbit-workflow
./rabbit-workflow/install.py /path/to/your/workspace   # explicit target
./rabbit-workflow/install.py                           # or install to $PWD
```

**curl** (installs to current directory)
```bash
cd /path/to/your/workspace
bash <(curl -fsSL https://raw.githubusercontent.com/USER/rabbit-workflow/main/install.py)
```

---

## Commands

| Command | Description |
|---|---|
| `/rabbit-refresh` | Manually re-inject policy |
| `/rabbit-config prompt-threshold N` | Set auto-refresh interval to N prompts (takes effect next session) |
| `/rabbit-config prompt-threshold` | Restore default auto-refresh interval |
| `/rabbit-config allowed-tools [add\|remove <tool>]` | Manage Claude Code tool permissions |
| `/rabbit-config bash-allow [add\|remove <cmd>]` | Manage Bash command permissions |
| `/rabbit-config permissions [lock\|unlock]` | Lock/unlock archive/ and test/ owner write bit |
| `/rabbit-config bypass-human-approval [true\|false]` | Manage Step 4 HUMAN-APPROVAL bypass (true=ACTIVE, false=OFF) |
| `/rabbit-project init <name>` | Scaffold a new project directory |

## Configuration

Default refresh interval: 20 prompts. Change with `/rabbit-config prompt-threshold N`.

## Applying rabbit anywhere

There is **one** work model. Every feature schema, every script, every
subagent works the same regardless of where the feature directory lives:
`.claude/features/<x>/` (rabbit improving itself), `projA/features/<y>/`
(any project applying the rabbit discipline), or any other path.

The TDD subagent is dispatched with a SCOPE per invocation; the
scope-guard hook enforces that scope. There is no rabbit-dev-mode vs
user-mode dichotomy in the runtime.

```bash
# Scaffold a new feature anywhere (Python — no .sh scripts in rabbit)
python3 .claude/features/rabbit-feature/scripts/new-feature.py \
    projA/features auth-redirect --owner alice

# Audit every feature in a tree (moved to rabbit-feature-audit skill in
# rabbit-feature)
Skill("rabbit-feature-audit", args: "projA/features")

# File a bug (rabbit-file owns bug/backlog item lifecycle)
python3 .claude/features/rabbit-file/scripts/file-item.py \
    --feature auth-redirect --type bug \
    --title "login redirects loop on safari" --priority high

# Transition TDD state — same script for any feature dir
python3 .claude/features/tdd-state-machine/scripts/tdd-step.py \
    transition projA/features/auth-redirect test-red

# Dispatch the TDD subagent onto a scope (sketched — typically the main session
# orchestrates this; the main session writes/removes the marker around the
# Agent call)
touch .rabbit-scope-active-auth-redirect
# (Agent dispatch with subagent_type: tdd-subagent, prompt with SCOPE: ...)
rm .rabbit-scope-active-auth-redirect
```

See `.claude/features/rabbit-cage/docs/spec/spec.md` for the rabbit-cage spec
and `.claude/features/tdd-subagent/docs/spec/spec.md` for the TDD subagent
protocol.

## Uninstall

Remove `.claude/` and `CLAUDE.md` from the installed workspace.
