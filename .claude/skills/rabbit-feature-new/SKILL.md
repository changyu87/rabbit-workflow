---
name: rabbit-feature-new
description: Scaffold a new rabbit feature directory with the standard skeleton (feature.json, docs/spec/spec.md, docs/spec/contract.md, test/run.py) in standalone mode, or scaffold a per-project plugin feature under .rabbit/rabbit-project/features/<name>/ with path-glob mapping in plugin mode. Use when the user asks to create, scaffold, or initialize a new rabbit feature — phrases like "create a new feature", "scaffold a feature called X", "/rabbit-feature-new", "set up a new rabbit feature", "bootstrap a feature dir". Invoke as Skill("rabbit-feature-new", args: "<feature-name>") in standalone mode or Skill("rabbit-feature-new", args: "<feature-name> <path-glob> [<path-glob>...]") in plugin mode.
version: 1.2.0
owner: rabbit-workflow team
deprecation_criterion: When this skill's scaffolding step is absorbed into a native `rabbit-feature` CLI subcommand or into the rabbit CLI itself.
---

# rabbit-feature-new — Feature Scaffolding Skill

Your job: create a new rabbit feature directory that conforms to the contract feature's structure rules, then verify it.

## Modes

This skill has two invocation modes. The mode is auto-detected from
`<repo>/.rabbit/.runtime/mode` (written at SessionStart by rabbit-meta's
`write_mode_marker`):

- **Standalone mode** (default; marker absent or contains `standalone`).
  Scaffolds a conforming rabbit-self feature directory under
  `.claude/features/<feature-name>/`.
- **Plugin mode** (marker contains `plugin`). Scaffolds a per-project
  feature under `<repo>/.rabbit/rabbit-project/features/<feature-name>/`
  and registers it in
  `<repo>/.rabbit/rabbit-project/project-map.json` with a list of
  user-code path globs.

## Inputs

**Standalone mode** — Args format: `<feature-name>`

- **feature-name**: lowercase kebab-case identifier (e.g., `rabbit-foo`,
  `my-tool`). The underlying scaffolder enforces naming rules and rejects
  invalid names.

**Plugin mode** — Args format: `<feature-name> <path-glob> [<path-glob>...]`

- **feature-name**: same naming rules as standalone.
- **path-glob**: one or more shell-style glob patterns, relative to the
  user-project root (the directory containing `.rabbit/`). Recursive
  globs (`**/*.py`) are supported. The scaffolder validates each glob
  against three rules and aborts on any failure:
  - Boundary: the glob's literal anchor must resolve under the
    user-project root (no `../../etc/**`).
  - Non-empty match: the union of matches must include at least one
    filesystem path (typo guard).
  - No overlap: no existing feature in `project-map.json` may already
    claim any matched path; on conflict the error names the incumbent.

## Protocol

The skill is a thin wrapper around an existing scaffolder. Follow these
steps in order; do not skip the validation step in standalone mode.

### Step 1 — Scaffold the directory

**Standalone mode.** Shell out to the rabbit-feature scaffolder, pointing
it at the rabbit features root and passing the requested feature name:

```bash
python3 .claude/features/rabbit-feature/scripts/new-feature.py \
  .claude/features <feature-name>
```

The script creates `.claude/features/<feature-name>/` with the standard
skeleton: `feature.json`, `docs/spec/spec.md`, `docs/spec/contract.md`,
`test/run.py`. It exits non-zero on invalid names or if the target already
exists — surface that error to the caller and stop.

**Plugin mode.** Shell out to the same scaffolder, but use the plugin
form (the script detects plugin mode from `.rabbit/.runtime/mode` itself,
so no flag is needed):

```bash
python3 .claude/features/rabbit-feature/scripts/new-feature.py \
  <feature-name> <path-glob> [<path-glob>...]
```

On success the scaffolder creates
`<repo>/.rabbit/rabbit-project/features/<feature-name>/` with
`feature.json`, `docs/spec/spec.md`, and `docs/spec/contract.md`; it also
registers the new feature in
`<repo>/.rabbit/rabbit-project/project-map.json` (schema-validated
against `.claude/features/contract/schemas/project-map.json.schema.json`
before write). On glob-validation failure (boundary, empty-match, or
overlap) it exits non-zero — surface that error to the caller and stop.

After a successful plugin-mode scaffold, the script prints a `NEXT:`
block to stdout naming the `rabbit-spec-create` skill (and equivalently
the `dispatch-spec-create.py` command) the caller should invoke to seed
`docs/spec/spec.md`. Capture that block and follow it (see Step 3 below);
the scaffolder itself never invokes the spec-creator subagent.

### Step 2 — Validate the scaffold

**Standalone mode only.** After the scaffolder succeeds, confirm the new
directory conforms by calling the contract feature's CLI shim around
`validate_feature`:

```bash
python3 .claude/features/contract/scripts/validate-feature.py .claude/features/<feature-name>
```

The shim exits 0 on pass, 1 on validation error, and 2 on bad invocation; it
prints the per-check messages to stdout on pass or stderr on fail. If
validation fails, do not silently continue; surface the failure so the caller
can decide whether to delete the partial scaffold or fix it in place.

**Plugin mode.** Skip this step — plugin-mode features live under
`.rabbit/rabbit-project/` and do not participate in the rabbit-self
audit surface. Glob-validation and project-map schema-validation already
ran inside the scaffolder.

### Step 3 — Invoke rabbit-spec-create (plugin mode only)

In plugin mode, the scaffolder's stdout ends with a `NEXT:` block of the
form:

```text
NEXT: invoke the rabbit-spec-create skill (or run the dispatcher
directly) to seed docs/spec/spec.md:
  Skill("rabbit-spec-create", args: "<feature-name> <glob1> <glob2> ...")
or equivalently:
  python3 .claude/features/rabbit-spec/scripts/dispatch-spec-create.py \
    --feature-name <feature-name> \
    --paths '<glob1>,<glob2>,...'
then dispatch the spec-creator subagent with the assembled prompt.
```

Invoke the `rabbit-spec-create` skill (preferred) which handles the
dispatch end-to-end. The user flow is therefore two steps:
(1) invoke this skill to scaffold; (2) invoke `rabbit-spec-create` to
draft the initial spec body.

In standalone mode this step does not apply — skip to Step 4. (Standalone
features can still invoke `rabbit-spec-create` if a seeded draft is
desired, but the scaffolder does not print the `NEXT:` block in that
mode.)

### Step 4 — Report the result

Report the absolute path of the new feature directory and a brief summary of
what was created. In plugin mode, also surface the path of the updated
`project-map.json` and the seeder-dispatch command from the `NEXT:`
block. Keep the report short — the caller already knows the request;
they just need confirmation and a path to navigate to.

## What You Do NOT Do

- Do not edit the generated skeleton files. The scaffolder is the source of
  truth for what a fresh feature looks like; if you want to change it, change
  the scaffolder, not the post-scaffold output.
- Do not invoke other skills. This skill is a small wrapper; it has no need
  to call out to `rabbit-feature-spec`, `rabbit-feature-touch`, or anything
  else. The caller decides what comes next.
- Do not skip the `validate_feature` check. A scaffold that doesn't pass
  contract validation is a latent bug — fail loudly instead.

## Notes

- The scaffolder lives at `.claude/features/rabbit-feature/scripts/new-feature.py`.
- The post-scaffold check uses `contract.lib.checks.validate_feature` (via
  the `validate-feature.py` CLI shim) so this skill stays in sync with
  whatever conformance rules `contract` owns — no rules are duplicated here.
