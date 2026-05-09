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
| `/rwf-refresh` | Manually re-inject policy |
| `/rwf-set-threshold N` | Set auto-refresh interval (takes effect next session) |

## Configuration

Default refresh interval: 20 prompts. Change with `/rwf-set-threshold N`.

## Applying rabbit to your own project

The feature schema and tooling are portable — they work on any directory,
not just `.claude/features/`. After installing rabbit into your workspace,
you can apply the same disciplined feature-oriented workflow to your own code:

```bash
# Scaffold a new feature in your project
bash .claude/features/user-features/scripts/new-feature.sh \
    projA/features auth-redirect --owner alice

# Sweep all features in projA, validating each against the schema
FEATURES_ROOT=projA/features \
    bash .claude/features/user-features/scripts/validate-all.sh

# File a bug under your project's bug tracker
BUG_ROOT=projA/bugs \
    bash .claude/features/bug-filing/scripts/file-bug.sh \
        --name 2026-05-09-login-loop --title "login redirects loop on safari" \
        --severity high --description "..." --related-feature auth-redirect

# Track TDD state for a user-mode feature
bash .claude/features/tdd-state-machine/scripts/tdd-step.sh \
    transition projA/features/auth-redirect test-red
```

The `breeder` and `claude-write-lockdown` rules apply ONLY to `.claude/`.
Your own project paths are yours to write directly.

See `.claude/features/user-features/spec.md` for the full guide.

## Uninstall

Remove `.claude/` and `CLAUDE.md` from the installed workspace.
