# Contract — policy-enforcement

## Reads

- `.claude/philosophy.md` — for the three load-bearing principles.
- `.claude/work-guide.md` — for the construction-rule sections.
- `CLAUDE.md` (repo root) — for the `@`-imports.

## Writes

**None.** This feature is a contract enforcer, not a content editor.

## Invokes

- `grep`, `wc` — for substring checks and size sanity.

## Inputs / Outputs

### `test/run.sh`

- **Inputs:** none (reads from the repo it lives in).
- **Stdout:** one `ok` / `FAIL` line per assertion, then a summary.
- **Exit:** `0` all assertions hold; `1` any assertion fails.

## Cross-scope handoff

- **Editing the content of `philosophy.md` / `work-guide.md`** — normal
  PR workflow. The breeder's system prompt requires an explicit spec PR
  to modify these (because they are the constitution).
- **Adding a new load-bearing section** — update both the file and this
  feature's `test/run.sh` (so the section is required going forward).
- **Removing a section** — first prove the workflow still functions
  without it, then update both file and test, then bump this feature's
  version.

## Versioning

- Current version: `1.0.0`.
- Adding a new required section is a breaking change for downstream
  consumers (e.g. external linters that scan for sections). Bump major.
- Removing a required section is also breaking.
- Tightening a sanity-size threshold (e.g. requiring philosophy.md to be
  > 1000 bytes instead of > 500) is breaking only if the current content
  doesn't meet the new threshold.
