# Contract — install-distribute

## Reads

- `install.sh` — the installer script (this feature owns its lifecycle but
  does not modify it).
- `<source>/.claude/` — when invoked in local mode, the source `.claude/`
  to copy from.
- `<source>/CLAUDE.md` — the policy anchor to copy.
- `<TARGET>/.claude/` — collision check (refuses if exists).
- `https://github.com/.../rabbit-workflow.tar.gz` — when invoked in
  download (curl-pipe) mode.

## Writes

- `<TARGET>/.claude/` — entire workflow footprint copied here.
- `<TARGET>/CLAUDE.md` — policy anchor.

**Nothing else.** The installer must NOT write `install.sh` itself, the
`test/` suite, the `archive/`, the `README.md`, or any other dev-only file
into the target. (This was an explicit fix in commit `d523bc8`: "strip
runtime files from install".)

## Invokes

- `git`, `curl`, `tar` — depending on install mode.
- Standard utilities: `cp -R`, `mkdir`, `mktemp`, `trap`.

## Inputs / Outputs

### `install.sh`

- **Argument:** Optional `TARGET` directory; defaults to `$PWD`.
- **Stdout:** progress messages.
- **Stderr:** error messages on collision or download failure.
- **Exit:** `0` success; `1` collision (target/.claude exists);
  non-zero on other failures (network, git, etc.).
- **Side effects:** creates `<TARGET>/.claude/` and `<TARGET>/CLAUDE.md`.

## Cross-scope handoff

- **Updating the workflow content** — handled by the rest of the rabbit
  workflow features (each owns its slice of `.claude/`). The installer is
  agnostic to what's inside `.claude/`; it copies whatever is present.
- **Uninstall** — out of scope. The user removes `.claude/` and `CLAUDE.md`
  manually; no uninstall script is shipped (deliberate: install is
  self-contained, uninstall is `rm -rf`).
- **Versioning the installed payload** — out of scope here. Versioning is
  per-feature (each `feature.json` carries a version).

## Versioning

- Current version: `1.0.0`.
- Adding a new install mode is non-breaking (additive).
- Changing the fail-safe behavior (e.g. allowing overwrite with `--force`)
  is non-breaking if opt-in; breaking if it changes the default.
- Removing the curl-pipe mode would be breaking.
