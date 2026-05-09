# Contract — rabbit-bug-handler

## Reads

- `.claude/docs/bugs/<bug-name>/bug.json` (target bug)
- `.claude/docs/bugs/<bug-name>/*` (any supporting files)
- `.claude/features/<related-feature>/feature.json` (when `related_feature` is set)
- `.claude/features/<related-feature>/spec.md`
- `.claude/features/<related-feature>/contract.md`
- `.claude/features/<related-feature>/test/` (to assess test-coverage gaps)

## Writes

**None.** This agent is read-only by design. Tools list deliberately omits
`Write` and `Edit` (statically enforced by the test).

## Invokes

- `bash .claude/features/bug-filing/scripts/list-bugs.sh` — to find related bugs.
- `bash .claude/features/bug-filing/scripts/bug-status.sh get <dir>` — to read status.
- `bash .claude/features/feature-skeleton/scripts/validate-feature.sh` — to assess
  whether the related feature is in a valid schema state.
- `git log` / `git blame` (read-only) — to check bug history if filed long ago.

## Inputs / Outputs

### Input (caller → bug-handler, via Agent tool prompt)

A free-form prompt naming the bug to triage. Recommended:

```
Triage bug <bug-name>. Bug dir: .claude/docs/bugs/<bug-name>/.
[Optional: any prior context the caller has.]
```

### Output (bug-handler → caller)

The structured `TRIAGE:` block described in `spec.md`. The block is
machine-parseable; surrounding prose is informational.

## Cross-scope handoff

The bug-handler emits `proposed_handoff:` lines that name the next agent
to dispatch. The caller (main session, typically) executes the handoff:

- For `.claude/` writes (closing bug, filing follow-up bug, transitioning
  feature TDD state): dispatch `breeder`.
- For test additions in a feature: dispatch the feature owner's preferred
  agent (often a `Plan` or implementation subagent), then `breeder` for
  the actual write.

## Versioning

- Current version: `1.0.0`.
- Adding a new classification is breaking (downstream parses the enum).
  Bump major.
- Adding a new field to the `TRIAGE:` block is breaking only if downstream
  parsers reject unknown fields. The contract instructs them not to;
  treat as additive.
- Removing a field from the `TRIAGE:` block is always breaking.
