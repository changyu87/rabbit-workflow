# install-distribute

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](./feature.json).
> Implementation files (NOT in this directory):
> - Installer: [`/install.sh`](../../../install.sh) (repo root)
> - Test suite: [`/test/test-install.sh`](../../../test/test-install.sh) (repo root)
> - User docs: [`/README.md`](../../../README.md) (repo root)

## Purpose

Distribute the rabbit workflow into a target workspace. Default install
copies just two artifacts: `.claude/` and `CLAUDE.md`. The runtime work
model (unified, scope-parameterized — see breeder spec) is identical
regardless of install variant.

This feature is a **documentation overlay** over the existing `install.sh`
and its test suite. The implementation predates the
`.claude/features/<name>/` schema and lives at the historical paths above.

## Install variants

| Variant | What's copied | When to use |
|---|---|---|
| **default** (no flag) | `.claude/` + `CLAUDE.md`; strips `.claude/docs/specs/*.md` and `.claude/docs/plans/*.md`; no `archive/` or `test/` | Most users. Minimal footprint, runtime is fully functional. |
| **`--all`** | Everything in default + `archive/` + `test/` + `.claude/docs/specs/` + `.claude/docs/plans/` kept | Rabbit fans / contributors who want a closer look at how rabbit is built. Inspection material only — runtime behavior unchanged. |

`--all` does NOT change runtime semantics. The same scope-guard hook,
the same breeder, the same TDD scripts. Only what's available on disk
for inspection differs.

## Two install modes (orthogonal to --all)

1. **Local (git clone) mode** — `SCRIPT_DIR/.claude` exists; the script
   copies directly from the local checkout.
2. **Download (curl-pipe) mode** — no local `.claude/`; the script
   downloads a GitHub tarball, extracts, copies.

Mode is auto-detected. Both work with or without `--all`.

```
# Local, default install
git clone https://github.com/USER/rabbit-workflow
./rabbit-workflow/install.sh /path/to/workspace

# Local, --all (for inspection)
./rabbit-workflow/install.sh --all /path/to/workspace
./rabbit-workflow/install.sh /path/to/workspace --all   # arg order flexible

# Curl-pipe, default install
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

`test/run.sh` (4 cases) sanity-checks installer presence, the fail-safe
on existing `.claude/`, and delegates to the full
`test/test-install.sh` suite at the repo root (17 cases including the new
`--all` variants — t10 through t15 cover default vs --all behavior, flag
ordering flexibility, and unknown-flag rejection; t16 regression-protects
the curl-pipe / stdin invocation mode against BASH_SOURCE unbound-variable
warnings).

The delegation pattern keeps the feature wrapper thin while the canonical
test suite remains where it has always been.
