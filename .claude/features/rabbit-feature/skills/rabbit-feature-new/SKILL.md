---
name: rabbit-feature-new
description: Scaffold a new rabbit feature directory with the standard skeleton (feature.json, docs/spec/spec.md, docs/spec/contract.md, test/run.py). Use when the user asks to create, scaffold, or initialize a new rabbit feature — phrases like "create a new feature", "scaffold a feature called X", "/rabbit-feature-new", "set up a new rabbit feature", "bootstrap a feature dir". Invoke as Skill("rabbit-feature-new", args: "<feature-name>").
version: 1.1.0
owner: rabbit-workflow team
deprecation_criterion: When this skill's scaffolding step is absorbed into a native `rabbit-feature` CLI subcommand or into the rabbit CLI itself.
---

# rabbit-feature-new — Feature Scaffolding Skill

Your job: create a new rabbit feature directory that conforms to the contract feature's structure rules, then verify it.

## Inputs

Args format: `<feature-name>`

- **feature-name**: lowercase kebab-case identifier (e.g., `rabbit-foo`, `my-tool`).
  The underlying scaffolder enforces the naming rules and will reject invalid names.

## Protocol

The skill is a thin wrapper around an existing scaffolder plus a conformance
check. Follow these four steps in order; do not skip the validation step.

### Step 1 — Scaffold the directory

Shell out to the rabbit-feature scaffolder, pointing it at the rabbit features
root and passing the requested feature name:

```bash
python3 .claude/features/rabbit-feature/scripts/new-feature.py \
  .claude/features <feature-name>
```

The script creates `.claude/features/<feature-name>/` with the standard
skeleton: `feature.json`, `docs/spec/spec.md`, `docs/spec/contract.md`,
`test/run.py`. It exits non-zero on invalid names or if the target already
exists — surface that error to the caller and stop.

### Step 2 — Validate the scaffold

After the scaffolder succeeds, confirm the new directory conforms by calling
the contract feature's CLI shim around `validate_feature`:

```bash
python3 .claude/features/contract/scripts/validate-feature.py .claude/features/<feature-name>
```

The shim exits 0 on pass, 1 on validation error, and 2 on bad invocation; it
prints the per-check messages to stdout on pass or stderr on fail. If
validation fails, do not silently continue; surface the failure so the caller
can decide whether to delete the partial scaffold or fix it in place.

### Step 3 — Report the result

Report the absolute path of the new feature directory and a brief summary of
what was created. Keep the report short — the caller already knows the
request; they just need confirmation and a path to navigate to.

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

- The scaffolder lives at `.claude/features/rabbit-feature/scripts/new-feature.py`
  (moved from rabbit-cage in RABBIT-CAGE-BACKLOG-26).
- The post-scaffold check uses `contract.lib.checks.validate_feature` (via
  the `validate-feature.py` CLI shim) so this skill stays in sync with
  whatever conformance rules `contract` owns — no rules are duplicated here.
