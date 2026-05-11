# rabbit-bug

Structured source of truth is feature.json.

## Purpose

Owns bug filing, tracking, and lifecycle for all rabbit features. Provides file-bug.sh, bug-status.sh, and list-bugs.sh. Bugs are stored under docs/bugs/BUG-ID/bug.json.

## Behavior

- file-bug.sh: Creates bug.json with fields: name, title, status (always open), severity, description, related_feature, filed, filed_by, closed, closed_by, history. description is never modified after filing.
- bug-status.sh: Reads or transitions bug status. The set subcommand supports optional --fix-commits and --touched-files that are stored in history when provided (omitted when absent). Enforces R7 for closing.
- list-bugs.sh: Lists bugs from all features by scanning feature.json files for bugs_root. Supports --status, --feature, --text filters.

## Out of scope

- Bug triage logic (contract/scripts/rabbit-triage.sh)
- Backlog items (rabbit-backlog)
- Feature scaffolding (rabbit-cage)

## Tests

test/run.sh runs 9 tests. Transitions via tdd-step.sh.
