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
| `/rabbit-refresh` | Manually re-inject policy |
| `/rabbit-config prompt-threshold N` | Set auto-refresh interval to N prompts (takes effect next session) |
| `/rabbit-config prompt-threshold` | Restore default auto-refresh interval |

## Configuration

Default refresh interval: 20 prompts. Change with `/rabbit-config prompt-threshold N`.

## Applying rabbit anywhere

There is **one** work model. Every feature schema, every script, every
subagent works the same regardless of where the feature directory lives:
`.claude/features/<x>/` (rabbit improving itself), `projA/features/<y>/`
(any project applying the rabbit discipline), or any other path.

The rabbit-breeder is dispatched with a SCOPE per invocation; the
scope-guard hook enforces that scope. There is no rabbit-dev-mode vs
user-mode dichotomy in the runtime.

```bash
# Scaffold a new feature anywhere
bash .claude/features/feature-scaffolder/scripts/new-feature.sh \
    projA/features auth-redirect --owner alice

# Sweep validate every feature in a tree
FEATURES_ROOT=projA/features \
    bash .claude/features/feature-scaffolder/scripts/validate-all.sh

# File a bug
BUG_ROOT=projA/bugs \
    bash .claude/features/bug-filing/scripts/file-bug.sh \
        --name 2026-05-09-login-loop --title "login redirects loop on safari" \
        --severity high --description "..." --related-feature auth-redirect

# Transition TDD state — same script for any feature dir
bash .claude/features/tdd-state-machine/scripts/tdd-step.sh \
    transition projA/features/auth-redirect test-red

# Dispatch the breeder onto a scope (sketched — typically the main session
# orchestrates this; the main session writes/removes the marker around
# the Agent call)
touch projA/features/auth-redirect/.rabbit-scope-active
# (Agent dispatch with subagent_type: rabbit-breeder, prompt with SCOPE: ...)
rm projA/features/auth-redirect/.rabbit-scope-active
```

See `.claude/features/feature-scaffolder/spec.md` for scaffolder details
and `.claude/features/breeder/spec.md` for the dispatcher protocol.

## Uninstall

Remove `.claude/` and `CLAUDE.md` from the installed workspace.
