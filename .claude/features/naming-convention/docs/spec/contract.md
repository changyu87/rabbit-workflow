# Contract — naming-convention

## Reads

- `<root>/.claude/commands/*.md` — basenames checked.
- `<root>/.claude/agents/*.md` — basenames checked.
- `<root>/.claude/skills/*/` — directory names checked.
- All files under `<root>/.claude/**` (excluding `<root>/.claude/docs/`) —
  basenames checked for legacy `rwf-` prefix.

## Writes

**None.** This feature is a detective enforcement check.

## Invokes

- `find` — to enumerate files for the rwf-ban scan, with `-prune` to skip
  `<root>/.claude/docs/`.
- `basename` — for path-to-name extraction.

## Inputs / Outputs

### `scripts/check-naming.sh [root]`

- **Inputs:** optional `root` (default `.`).
- **Stdout:** `OK: ...` summary on success.
- **Stderr:** one `VIOLATION:` line per offending file, then
  `FAIL: N naming violation(s) under <root>/.claude`.
- **Exit:** `0` conformant; `1` violations; `2` bad root.

## Cross-scope handoff

- **Adding a new artifact kind** (e.g. a new `.claude/<kind>/` directory
  that should be name-checked) — extend the validator and tests, bump
  version.
- **Tolerating a non-rabbit file** (rare; e.g. a fixture or vendored file)
  — add an explicit ignore in the validator. Don't fork the rule per file.
- **Renaming a live artifact** — handled outside this feature; `breeder`
  performs the actual `git mv` and reference updates.

## Versioning

- Current version: `1.0.0`.
- Adding a new banned prefix is breaking (existing names that newly hit
  the ban must rename). Bump major.
- Loosening a rule (e.g. allowing a new prefix) is non-breaking if old
  names still pass.
- Adding a new ignored basename (e.g. `LICENSE.md`) is non-breaking.
