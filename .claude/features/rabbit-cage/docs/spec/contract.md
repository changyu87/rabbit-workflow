# rabbit-cage — Contract

**Version**: 1.0.0
**Owner**: rabbit-workflow team

---

## Provides

All files listed under "Owned Files" in `spec.md`:

- `rabbit-cage/agents/` — agent definition `.md` files
- `rabbit-cage/commands/` — slash command `.md` files
- `rabbit-cage/hooks/rbt-refresh.sh`
- `rabbit-cage/hooks/scope-guard.sh`
- `rabbit-cage/skills/` — empty until a skill is added
- `rabbit-cage/settings.json` — the Claude Code settings object
- `rabbit-cage/CLAUDE.md`
- `rabbit-cage/README.md`
- `rabbit-cage/install.sh`

---

## Reads

Nothing from other features at runtime. Symlink wiring is performed at install time by `relink.sh`, not by any runtime rabbit-cage script.

---

## Invokes

- `relink.sh` — called by `install.sh` at install time to wire all symlinks from the surface paths to their targets inside `rabbit-cage/`.

---

## Never Does

- Modifies other features' directories.
- Writes `settings.local.json`.
- Reads or generates any artifact outside `.claude/features/rabbit-cage/` at runtime.
