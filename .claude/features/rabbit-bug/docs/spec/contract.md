# Contract -- rabbit-bug

## Reads

- .claude/features/*/feature.json (for bugs_root field)
- .claude/features/registry.json (for feature path lookup)
- docs/bugs/*/bug.json (read and update)
- docs/bugs/*/vet-triage.json (R7 enforcement)
- docs/bugs/*/tdd-gap.json (R7 enforcement)

## Writes

- docs/bugs/BUG-ID/bug.json (created by file-bug.sh, updated by bug-status.sh)

## Invokes

- jq (for JSON manipulation)
- git (for REPO_ROOT detection in file-bug.sh)
- python3 (in list-bugs.sh for feature.json parsing)
- find (in list-bugs.sh)

## Inputs / Outputs

- file-bug.sh: takes --title, --severity, --description, optionally --related-feature, --filed-by. Writes bug.json, prints filed path.
- bug-status.sh get DIR: prints current status.
- bug-status.sh set DIR STATUS --note R [...]: transitions status, updates bug.json.
- list-bugs.sh: prints JSON array or text of bug summaries.

## Versioning

- Current version: 0.1.0
- Bump rules: minor for new arguments; major for schema changes.
- Deprecation criterion: when rabbit features are retired or a unified tracking system replaces file-based bugs.
