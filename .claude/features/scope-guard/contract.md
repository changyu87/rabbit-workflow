# Contract — scope-guard

## Reads

- The PreToolUse JSON payload on stdin (provided by Claude Code).
- The target path's filesystem ancestors (looking for `.rabbit-scope-active`
  and `feature.json` markers).
- `.claude/settings.json` (only by virtue of being wired in via PreToolUse;
  the hook itself does not read settings).

## Writes

**None.** This feature is purely a detective/blocking hook. It denies
out-of-scope writes; it does not write anything itself.

## Invokes

- `jq` — for JSON parsing of stdin.
- `grep`, `sed`, `awk`, `tr` — for Bash command parsing.
- Standard utilities: `dirname`, `basename`, `cat`, `printf`.

## Inputs / Outputs

### `.claude/hooks/scope-guard.sh`

- **Stdin:** PreToolUse JSON, e.g.
  ```json
  {"tool_name":"Write","tool_input":{"file_path":"/path/to/file","content":"..."}}
  ```
- **Stdout:** none on success.
- **Stderr:** `scope-guard: DENY <reason>` on out-of-scope detection.
- **Exit:** `0` allow, `2` deny (per Claude Code hook convention; non-zero
  blocks the tool call).

## Cross-scope handoff

- **Setting/clearing the scope marker** — out of scope (no pun intended).
  The dispatcher protocol is documented in `breeder/spec.md`.
- **Adding new write patterns** to the Bash parser — extend
  `extract_bash_targets()` in the hook script. New patterns are additive
  (more denials) — bump minor version.
- **Removing a write pattern** is breaking (previously-blocked writes
  start passing through).

## Versioning

- Current version: `1.0.0`.
- Adding a Bash-write-pattern detector is non-breaking but a minor bump
  (more strict).
- Loosening the marker semantics (e.g. allowing in-process state instead
  of file marker) is a major bump.
- Removing the marker exemption (`.rabbit-scope-active` file always
  allowed) would break the dispatcher protocol — major bump.
