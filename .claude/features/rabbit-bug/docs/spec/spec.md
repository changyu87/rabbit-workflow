# rabbit-bug

Structured source of truth is feature.json.

## Tech Stack

All runtime scripts and test harnesses are Python 3. Bash is not used in this feature.

## Purpose

Owns bug filing, tracking, and lifecycle for all rabbit features. Provides file-bug.py, bug-status.py, and list-bugs.py. Bugs are stored under docs/bugs/BUG-ID/bug.json.

Bug lifecycle is version-controlled: `file-bug.py` commits the new `bug.json`
to git after creation, and every `bug-status.py set` transition commits the
mutated `bug.json`. This makes the audit trail inspectable through `git log`
in addition to the in-file `history` array. Git commit failures are silent
(non-fatal) so that lifecycle operations succeed even outside a git
worktree.

## Behavior

- file-bug.py: Creates bug.json with fields: name, title, status (always open), severity, description, related_feature, filed, filed_by, closed, closed_by, history. description is never modified after filing. Commits the new bug.json to git. Resolves the canonical bug storage path for a given feature by invoking `workspace-map.sh` from the rabbit-workspace-map contract interface rather than constructing paths by convention.
- bug-status.py: Reads or transitions bug status. The `set` subcommand requires `--reason <text>` on every transition (missing or empty value exits 1). When transitioning to `closed`, `--fix-commits <sha>[,<sha>...]` is required unless `--skip-vet-reason <text>` is provided (the skip-vet path is the existing emergency bypass that also satisfies R7). `--fix-commits` is rejected when transitioning to `refused`. Optional `--touched-files` is stored in history when provided. After every successful `set`, the mutated `bug.json` is committed to git.
- list-bugs.py: Lists bugs from all features by invoking `workspace-map.sh` from the rabbit-workspace-map contract interface to resolve the canonical bug storage path per feature, rather than constructing paths by convention. Supports --status, --feature, --text filters. The --text output format is `NAME  [STATUS]  [SEVERITY]  TITLE`.

## Out of scope

- Bug triage logic (contract/scripts/rabbit-triage.sh)
- Backlog items (rabbit-backlog)
- Feature scaffolding (rabbit-cage)

## Invariants

- surface.skills in feature.json MUST be []. Skills are managed via explicit copy-file entries in build-contract.json; the surface.skills declaration is retired.
- file-bug.py MUST check if the current git branch is `main` before committing. If the current branch is not `main`, it MUST print a warning to stderr and prompt the user for explicit confirmation by reading from /dev/tty. If /dev/tty is unavailable or the user does not confirm, file-bug.py MUST exit non-zero without filing.
- SKILL.md Working Protocol MUST include a user-decision gate after the eval subagent returns its verdict: the skill MUST brief the user with a summary of the eval findings and a recommendation, then ask whether to refuse or work the item — it MUST NOT dispatch rabbit-feature-touch until the user confirms.

## Tests

test/run.py runs all test suites. Transitions via tdd-step.py.
