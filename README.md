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

## Uninstall

Remove `.claude/` and `CLAUDE.md` from the installed workspace.
