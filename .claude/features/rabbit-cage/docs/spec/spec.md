# rabbit-cage — Specification

**Version**: 1.0.0
**Owner**: rabbit-workflow team
**Deprecation criterion**: when Claude Code exposes a native feature-container mechanism that subsumes this role

---

## Purpose

rabbit-cage is the single feature that owns the Claude Code surface of the rabbit workflow.

Claude Code reads from the following paths:
- `.claude/agents/` — subagent definition files
- `.claude/commands/` — slash command files
- `.claude/hooks/` — lifecycle hook scripts
- `.claude/skills/` — skill files
- `.claude/settings.json` — Claude Code settings
- `CLAUDE.md` — project instructions
- `README.md` — repository root readme
- `install.sh` — installer script

All of these paths are symlinks whose targets live inside `rabbit-cage/`. Other features declare their surface in their own `feature.json`; rabbit-cage is the container that exposes that surface to Claude Code via symlinks. rabbit-cage does not own the content of other features — it owns the wiring layer.

---

## Invariants

The following symlinks must exist at all times. Any deviation is a bug.

| Symlink | Target |
|---------|--------|
| `.claude/agents/` | `.claude/features/rabbit-cage/agents/` |
| `.claude/commands/` | `.claude/features/rabbit-cage/commands/` |
| `.claude/hooks/` | `.claude/features/rabbit-cage/hooks/` |
| `.claude/skills/` | `.claude/features/rabbit-cage/skills/` |
| `.claude/settings.json` | `.claude/features/rabbit-cage/settings.json` |
| `.claude/policy/` | `.claude/features/policy/` |
| `.claude/contract/` | `.claude/features/contract/` |
| `$ROOT/CLAUDE.md` | `.claude/features/rabbit-cage/CLAUDE.md` |
| `$ROOT/README.md` | `.claude/features/rabbit-cage/README.md` |
| `$ROOT/install.sh` | `.claude/features/rabbit-cage/install.sh` |

Additional invariants:
- `CLAUDE.md` `@`-imports from `.claude/policy/` (not old flat files).
- The `root-management` feature does not exist; it has been absorbed by rabbit-cage.

---

## Owned Files

The actual files live here; surface paths are symlinks into these locations.

- `rabbit-cage/agents/` — agent definition `.md` files
- `rabbit-cage/commands/` — slash command `.md` files
- `rabbit-cage/hooks/rbt-refresh.sh` — auto-refresh hook
- `rabbit-cage/hooks/scope-guard.sh` — scope-guard PreToolUse hook
- `rabbit-cage/skills/` — empty until a skill is added
- `rabbit-cage/settings.json` — the Claude Code settings object
- `rabbit-cage/CLAUDE.md` — project instructions (root symlink target)
- `rabbit-cage/README.md` — repository readme (root symlink target)
- `rabbit-cage/install.sh` — installer that wires all symlinks via relink.sh

---

## Out of Scope

- Content authored by other features (policy, contract, auto-refresh, etc.) — rabbit-cage wires their surface but does not own their content.
- `settings.local.json` — user-local overrides; never written by rabbit-cage.
- Any file outside `.claude/features/rabbit-cage/` and the symlinks it wires.
