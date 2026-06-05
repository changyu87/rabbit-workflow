---
name: rabbit-feature-audit
description: Validate one rabbit feature or sweep every feature for contract conformance. Use when the user asks to audit, validate, lint, or check rabbit features — phrases like "audit all features", "validate rabbit-foo", "check feature conformance", "/rabbit-feature-audit", "are all features OK", "run the feature checker". Invoke as Skill("rabbit-feature-audit", args: "all") to sweep every feature, or Skill("rabbit-feature-audit", args: "<feature-name>") to audit a single feature.
version: 1.3.0
owner: rabbit-workflow team
deprecation_criterion: When contract.lib.checks.validate_feature is exposed via a first-class CLI in the contract feature.
---

# rabbit-feature-audit — Feature Audit Skill

Your job: validate rabbit feature directories against the contract feature's
conformance rules and return a structured pass/fail finding per feature.

## Inputs

Args format: `all` | `<feature-name>`

- **`all`** — sweep every directory under `.claude/features/`.
- **`<feature-name>`** — audit only the named feature
  (e.g., `rabbit-foo`, `tdd-subagent`).

## Protocol

The skill is a thin wrapper around `contract.lib.checks.validate_feature` —
the contract feature owns the actual conformance rules, so this skill stays
in sync with them automatically.

### Step 1 — Resolve the targets

- `all`: list every immediate subdirectory of `.claude/features/`
  (skip non-directories and dotfiles).
- `<feature-name>`: resolve to `.claude/features/<feature-name>/`. If the
  directory does not exist, report that and stop.

### Step 2 — Validate each target

For each target directory, call the contract feature's CLI shim around
`validate_feature`:

```bash
python3 .claude/features/contract/scripts/validate-feature.py <feature-dir>
```

The shim exits 0 on pass, 1 on validation error, and 2 on bad invocation; it
prints the per-check messages to stdout on pass or stderr on fail. Collect
the exit code and messages per target so Step 3 can render them uniformly.

Then run the rabbit-feature-owned team-owner check on the same target:

```bash
python3 .claude/features/rabbit-feature/scripts/audit-owner.py <feature-dir>
```

This enforces that every repo-level feature's `feature.json` `owner` is
exactly `rabbit-workflow team`. Repo-level features
distributed as part of rabbit-workflow MUST be team-owned, never owned by an
individual; an individual owner FAILS the audit with a message naming the
offending feature and its current owner. The script exits 0 on pass (or for
a feature exempted by contract Inv 36's status short-circuit), 1 on owner
mismatch, and 2 on bad invocation. Fold its
exit code and message into the per-feature finding: a target PASSES only when
BOTH `validate-feature.py` and `audit-owner.py` pass.

Notes on semantics owned by `validate_feature`:
- A feature exempted by contract Inv 36's status short-circuit returns
  `passed=True` with a status note. Do not skip such features yourself; let
  `validate_feature` handle the short-circuit so the rule lives in one place.

### Step 3 — Report the results

Emit a per-feature pass/fail list with the messages from each `CheckResult`.
Keep the structure stable so callers can parse it:

```
- <feature-name>: PASS | FAIL
    <message 1>
    <message 2>
    ...
```

For `all`, also emit a one-line summary: total features, pass count,
fail count. Exit non-zero overall if any feature fails so a wrapping
caller can detect breakage.

## What You Do NOT Do

- Do not modify any feature files. This skill is read-only; remediation
  belongs to the owning feature's TDD cycle.
- Do not invoke other skills. This skill is a small wrapper; the caller
  decides what to do with the findings.
- Do not skip features based on your own heuristics. The status
  short-circuit and any future exemptions live inside `validate_feature`
  so the rules stay centralized.

## Notes

- This skill is the cross-feature audit sweep. Reach for it whenever you
  need to validate one feature or every feature.
