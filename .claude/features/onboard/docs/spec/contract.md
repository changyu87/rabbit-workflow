# onboard — Contract

**Version:** 1.0.0
**Owner:** rabbit-workflow team

## Provides

- `scripts/rabbit-project.sh` — CLI for scaffolding and maintaining project directories
- `.claude/commands/rabbit-project.md` — slash command stub for Claude Code

## Reads

- `project-{name}/project-map.json` — project source map
- `project-{name}/features/registry.json` — project-local feature registry
- `.claude/features/contract/templates/project-map-template.json` — template for new project maps
- `.claude/features/contract/templates/registry-template.json` — template for new feature registries

## Writes

- `project-{name}/project-map.json` — created by `init`, updated by `set-path` and `map`
- `project-{name}/features/registry.json` — created by `init`
- `project-{name}/features/` directory — created by `init`
- `project-{name}/contract/` directory — created by `init`

## Never does

- Modify `.claude/features/registry.json` (the rabbit-internal registry)
- Modify any file under `.claude/features/` directly
- Modify any rabbit-internal feature's files
- Perform interactive I/O (no prompts, no stdin reads)
