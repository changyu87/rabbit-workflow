# Contract — subagent-policy-injection

## Reads

- `<repo>/.claude/philosophy.md` — required canonical file.
- `<repo>/.claude/work-guide.md` — required canonical file.
- Any path passed via `--include <path>` — must exist or error before any
  output is emitted.

## Writes

**None.** This feature is a pure stdout emitter.

## Invokes

- `cat`, `basename`, `sed` — standard shell utilities.

## Inputs / Outputs

### `scripts/policy-block.sh [--include <path>]...`

- **Inputs:** zero or more `--include` flags. Order is preserved in output.
- **Stdout:** the canonical policy block (see spec.md for shape).
- **Stderr:** `ERROR: ...` for missing `--include` path or unknown arg.
- **Exit:** `0` success, `1` missing canonical or `--include` file,
  `2` invocation error.

## Cross-scope handoff

- **Modifying the framing tone** — direct edit of the heredoc inside
  `policy-block.sh`. Bump version (the framing IS the contract — LLMs
  parse the visual structure).
- **Adding a default `--include` set** — out of scope for v1. Today every
  caller chooses includes per dispatch. If a need arises (e.g.
  "always-include hard-rules.md"), bump version and document.
- **Subagent-side block verification** — out of scope. No mechanism today.

## Versioning

- Current version: `1.0.0`.
- Adding a new optional flag (e.g. `--max-bytes N` to cap output) is
  non-breaking.
- Changing the visual framing (banner characters, divider style) is
  breaking — existing subagent prompts are tuned to the current shape.
  Bump major.
- Removing the `--include` flag is breaking.
- Switching the canonical file paths (e.g. moving `philosophy.md`) requires
  coordinated update with `policy-enforcement` feature.
