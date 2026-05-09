# Contract — rabbit-breeder

## Reads

- `<repo>/.claude/philosophy.md`, `<repo>/.claude/work-guide.md` —
  re-read on every dispatched task.
- Existing `<SCOPE>/feature.json`, `<SCOPE>/spec.md`, `<SCOPE>/contract.md`
  for the target feature.
- The caller's structured request (passed via Agent tool prompt; must
  include `SCOPE` field).

## Writes

- Anything under `<SCOPE>` — but only what the caller's request names.
  Out-of-scope writes are refused with `REJECTED: out-of-scope`.
- The scope-guard hook denies any Write/Edit/Bash whose target is not
  under a directory containing `.rabbit-scope-active`. The dispatcher
  is responsible for placing/removing that marker.

## Invokes

- `bash <repo>/.claude/features/feature-skeleton/scripts/validate-feature.sh
  <SCOPE>` — after any feature directory write.
- `bash <repo>/.claude/features/tdd-state-machine/scripts/tdd-step.sh
  <subcmd> <SCOPE> ...` — for state transitions.
- `bash <repo>/.claude/features/tdd-state-machine/scripts/tdd-drift-check.sh
  <SCOPE>` — after transitions.
- `git` — branch, add, commit, push.
- `gh pr create` — open PRs. (`gh pr merge` is denied at the permission
  layer; the breeder does not attempt to call it.)
- `jq` — for surgical JSON edits to `feature.json` files.

## Inputs / Outputs

### Input (caller → breeder, via Agent tool prompt)

A structured request containing:

```
SCOPE:        <directory the breeder may write within (REQUIRED)>
operation:    <create_feature | update_feature | transition_state | add_bug | edit_file | delete_file>
target:       <relative path inside SCOPE>
payload:      <operation-specific data>
tdd_context:  <optional, output of tdd-context.sh for SCOPE>
reason:       <one sentence justifying the change>
```

The dispatcher must `touch <SCOPE>/.rabbit-scope-active` before invoking
and `rm` it after the breeder returns. The scope-guard hook depends on
this marker.

### Output (breeder → caller, in last message)

```
RESULT:           <success | rejected | clarify>
SCOPE:            <the scope the breeder operated under>
REASON:           <one-line summary>
FILES_CHANGED:    <list of paths inside SCOPE, or "none">
COMMITS:          <list of commit SHAs, or "none">
TDD_STATE_AFTER:  <state, or "n/a">
NEXT_RECOMMENDED: <e.g. "open PR", "run drift check", "file follow-up bug">
```

## Cross-scope handoff

- **Implementation work outside `<SCOPE>`** — refused. Caller dispatches a
  separate breeder for each scope.
- **PR merge** — refused. Caller (a human, or a merge-authorized agent in
  the future) handles merge after review.
- **Editing the workflow constitution (`philosophy.md` / `work-guide.md`)**
  — refused unless `<SCOPE>` actually covers those files AND the caller's
  prompt names an explicit constitution-update spec PR.
- **Multi-feature requests** — refused. Caller dispatches once per feature
  with the appropriate `<SCOPE>` each time.

## Versioning

- Current version: `1.0.0`.
- Adding a new `operation` is non-breaking (additive). Removing one is
  breaking.
- Adding a required input field (e.g. promoting `tdd_context` from
  optional to required) is breaking.
- Removing the `SCOPE` field would be breaking and would defeat the
  unified work model.
