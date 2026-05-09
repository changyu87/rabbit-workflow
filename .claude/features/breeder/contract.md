# Contract — breeder

## Reads

- `.claude/philosophy.md`, `.claude/work-guide.md` — re-read on every
  dispatched task.
- Existing `.claude/features/<name>/feature.json`, `spec.md`, `contract.md`
  for the target feature(s).
- The caller's structured request (passed via Agent tool prompt).

## Writes

- Anything under `.claude/**` — but only what the caller's request names.
  Out-of-scope writes are refused with `REJECTED: out-of-scope`.

## Invokes

- `bash .claude/features/feature-skeleton/scripts/validate-feature.sh` —
  after any feature directory write.
- `bash .claude/features/tdd-state-machine/scripts/tdd-step.sh` — for state
  transitions.
- `bash .claude/features/tdd-state-machine/scripts/tdd-drift-check.sh` —
  after transitions.
- `git` — branch, add, commit, push.
- `gh pr create` — open PRs. (`gh pr merge` is denied at the permission
  layer; the breeder does not attempt to call it.)
- `jq` — for surgical JSON edits to `feature.json` files.

## Inputs / Outputs

### Input (caller → breeder, via Agent tool prompt)

A structured request containing:

```
operation:    <create_feature | update_feature | transition_state | add_bug | edit_file | delete_file>
target:       <path under .claude/>
payload:      <operation-specific data>
tdd_context:  <optional, output of tdd-context.sh for the target feature>
reason:       <one sentence justifying the change>
```

### Output (breeder → caller, in last message)

```
RESULT:           <success | rejected | clarify>
REASON:           <one-line summary>
FILES_CHANGED:    <list of paths, or "none">
COMMITS:          <list of commit SHAs, or "none">
TDD_STATE_AFTER:  <state, or "n/a">
NEXT_RECOMMENDED: <e.g. "open PR", "run drift check", "file follow-up bug">
```

## Cross-scope handoff

- **Implementation work outside `.claude/`** — refused. Caller dispatches a
  different agent.
- **PR merge** — refused. Caller (a human, or a merge-authorized agent in
  the future) handles merge after review.
- **Editing `philosophy.md` / `work-guide.md`** — refused unless the
  caller's prompt explicitly names a constitution-update spec PR. These are
  the workflow's constitution; changes are deliberate.
- **Multi-feature requests** — refused. Caller dispatches once per feature.

## Versioning

- Current version: `1.0.0`.
- Adding a new `operation` is non-breaking (additive). Removing one is
  breaking.
- Changes to the input/output contract format are breaking and require a
  major bump and a deprecation window.
