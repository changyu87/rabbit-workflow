# install-distribute

> Source of truth: [`feature.json`](./feature.json).
> Implementation files (NOT in this directory):
> - Installer: [`/install.sh`](../../../install.sh) (repo root)
> - Test suite: [`/test/test-install.sh`](../../../test/test-install.sh) (repo root)
> - User docs: [`/README.md`](../../../README.md) (repo root)

## Purpose

Distribute the rabbit workflow into a target workspace by copying just two
artifacts: `.claude/` and `CLAUDE.md`. Everything else (the installer, this
feature directory, archived docs, the test suite, the README) stays in the
source repo and never reaches the user's workspace.

This feature is a **documentation overlay** over the existing `install.sh`
and its test suite. The implementation predates the
`.claude/features/<name>/` schema and lives at the historical paths above.

## Two install modes

1. **Local (git clone) mode** — `SCRIPT_DIR/.claude` exists; the script
   copies directly.
2. **Download (curl-pipe) mode** — no local `.claude/`; the script
   downloads a GitHub tarball, extracts, copies.

Mode is auto-detected. The README documents both invocations:

```
# Local
git clone https://github.com/USER/rabbit-workflow
./rabbit-workflow/install.sh /path/to/workspace

# Curl
cd /path/to/workspace
bash <(curl -fsSL https://raw.githubusercontent.com/USER/rabbit-workflow/main/install.sh)
```

## Fail-safe

If `TARGET/.claude` already exists, `install.sh` exits 1 with a clear
message. This protects against accidental overwrite when the user has
already installed (or has their own `.claude/` for unrelated reasons).

## What this feature does NOT define

- The contents of `.claude/` itself — that is the rest of the rabbit
  workflow (every other feature).
- The CLAUDE.md template — defined by the `policy-enforcement` feature
  (which owns the policy anchor file).
- The slash commands invoked from a user's workspace — defined by their
  respective features (`auto-refresh` defines `/rwf-refresh` and
  `/rwf-set-threshold`).

## Tests

`test/run.sh` (4 cases):

- t1: `install.sh` exists and is executable.
- t2: `test/test-install.sh` exists and is executable.
- t3: Running `install.sh` against a directory that already has `.claude/`
  refuses (sanity check of the fail-safe).
- t4: Delegates to the full existing `test/test-install.sh` suite (which
  exercises clean install, file permissions, settings.json content,
  CLAUDE.md imports, fail-safe on existing `.claude/`, no-arg default,
  hook JSON output, threshold command validation).

This delegation pattern keeps the feature wrapper thin while the canonical
test suite remains where it has always been (`test/test-install.sh` at the
repo root).
