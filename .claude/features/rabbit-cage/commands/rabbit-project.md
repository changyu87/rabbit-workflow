# /rabbit-project

Scaffold and maintain project directories managed by rabbit.

> Scaffold and manage user project directories — not a status command.

## Usage

/rabbit-project init <name>
/rabbit-project set-path <name> <absolute-path>
/rabbit-project map <name> <source-path> <feature-name>

## Implementation

Delegates to `.claude/features/rabbit-cage/scripts/rabbit-project.py`,
which handles `init` directly and dispatches the other subcommands to the
per-subcommand Python scripts:

- `set-path`    → `.claude/features/rabbit-cage/scripts/rabbit-project-set-path.py`
- `map`         → `.claude/features/rabbit-cage/scripts/rabbit-project-map.py`
