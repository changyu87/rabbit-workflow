# Contract -- rabbit-bug

## Reads

- .claude/features/*/feature.json (for bugs_root field)
- .claude/features/registry.json (for feature path lookup)
- docs/bugs/*/bug.json (read and update)
- docs/bugs/*/vet-triage.json (R7 enforcement)
- docs/bugs/*/tdd-gap.json (R7 enforcement)

## Writes

- docs/bugs/BUG-ID/bug.json (created by file-bug.sh, updated by bug-status.sh)
- Git commits — `file-bug.sh` commits the newly created `bug.json`;
  `bug-status.sh set` commits the mutated `bug.json` after every successful
  transition. Commit messages follow the form
  `bug: <BUG-ID> <old-status> -> <new-status> (<reason summary>)` for
  transitions and `bug: file <BUG-ID> (<title>)` for creation. Git commit
  failures are silent (non-fatal).

## Invokes

- jq (for JSON manipulation)
- git (for REPO_ROOT detection in file-bug.sh; `git add` and `git commit`
  after filing and after every status transition)
- python3 (in list-bugs.sh for feature.json parsing)
- find (in list-bugs.sh)

## Inputs / Outputs

- file-bug.sh: takes --title, --severity, --description, optionally --related-feature, --filed-by. Writes bug.json, prints filed path, and commits the new bug.json to git.
- bug-status.sh get DIR: prints current status.
- bug-status.sh set DIR STATUS --reason R [--fix-commits <sha>[,<sha>...]] [--skip-vet-reason R] [--touched-files ...]:
  - `--reason` is required on every `set` invocation (missing or empty exits 1).
  - `--fix-commits` is required when `STATUS` is `closed` and is the only acceptable proof of vet completion unless `--skip-vet-reason` is supplied (existing emergency bypass per R7).
  - `--fix-commits` is rejected when `STATUS` is `refused`.
  - On success, the mutated bug.json is committed to git.
- list-bugs.sh: prints JSON array or text of bug summaries.

## Versioning

- Current version: 1.0.0
- Bump rules: minor for additive new arguments; major for CLI flag renames or
  enforcement changes.
- Breaking changes in 1.0.0 (from 0.1.0):
  - `--note` renamed to `--reason` on `bug-status.sh set` (unifies with
    rabbit-backlog terminology).
  - `--reason` is now required on every transition (previously optional).
  - `--fix-commits` is now required on transitions to `closed` (unless
    `--skip-vet-reason` is provided), and rejected on transitions to
    `refused`.
  - New behavior: `file-bug.sh` and `bug-status.sh set` produce git commits.
- Migration: callers using `--note` must rename to `--reason`; no coexistence
  window because callers are local to this repo and the substitution is
  trivial. Pre-1.0.0 history entries with `note` field remain readable
  (description-only field, not interpreted by the CLI).
- Deprecation criterion: when rabbit features are retired or a unified tracking system replaces file-based bugs.
