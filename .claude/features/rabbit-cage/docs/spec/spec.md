---
feature: rabbit-cage
version: 3.8.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native feature-container mechanism that subsumes this role
status: active
---

# rabbit-cage — Spec

## Purpose

rabbit-cage owns the Claude Code surface layer of the rabbit workflow, exposing all feature content to Claude Code via symlinks and committed generated artifacts.

## Surface

- `.claude/commands/` — symlink to `rabbit-cage/commands/`
- `.claude/hooks/` — symlink to `rabbit-cage/hooks/`
- `.claude/skills/` — directory of recursive copies (`cp -rp`) of feature skill source dirs; committed to the repo
- `.claude/settings.json` — symlink to `rabbit-cage/settings.json`
- `.claude/features/rabbit-cage/skills/rabbit-config/` — `/rabbit-config` skill source directory (SKILL.md + scripts/)
- `.claude/policy/` — symlink to `.claude/features/policy/`
- `.claude/contract/` — symlink to `.claude/features/contract/`
- `CLAUDE.md` — generated file (by `generate-claude-md.py`); committed to the repo (not gitignored); not a symlink; validated on every Stop against a fresh regeneration from policy sources
- `README.md` — symlink to `rabbit-cage/README.md`
- `install.py` — copy of `rabbit-cage/install.py` (Python bootstrap installer; see Tech Stack section)

## Invariants

1. `.claude/commands` is a symlink pointing to `.claude/features/rabbit-cage/commands`.
2. `.claude/hooks` is a symlink pointing to `.claude/features/rabbit-cage/hooks`.
3. `.claude/skills` is a real directory (not a symlink) populated by `build.py` (via `build-contract.json` copy-file targets) from each feature's skill source directory; the directory and its contents are committed to the repo (not gitignored).
4. `.claude/settings.json` is a symlink pointing to `.claude/features/rabbit-cage/settings.json`.
5. `.claude/policy` is a symlink pointing to `.claude/features/policy`.
6. `.claude/contract` is a symlink pointing to `.claude/features/contract`.
7. `CLAUDE.md` at repo root is a generated regular file (not a symlink); produced by `generate-claude-md.py`; committed to the repo (not gitignored); contains inline `rabbit-policy-start`/`rabbit-policy-end` section.
8. `README.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/README.md`.
9. `install.py` at repo root is a copy of `.claude/features/rabbit-cage/install.py` (managed by `build-contract.json`). `install.py` is the bootstrap installer; it is a standalone Python script requiring only the stdlib. No `.sh` files exist in rabbit-cage.
10. `CLAUDE.md` contains `@`-imports sourcing files from `.claude/policy/`.
10a. The CLAUDE.md header (everything before the `@`-import lines) is sourced from the `header` field of `.claude/features/rabbit-cage/policy-header.json` via `generate-claude-md-header.py`. The header MUST orient a fresh session to the rabbit workflow by stating: (a) the workflow name as an H1, (b) the four core traits as bullets — **Feature-oriented**, **Scope-protected**, **Drift-protected**, **Subagent-driven**, (c) a token-cost judgment note as a trailing bullet on the same list, and (d) a final paragraph naming the reader as "the dispatcher" and forbidding direct edits to scope-protected files without explicit human approval. The exact text is fixed by the `header` field value and verified by `test-claude-md-header.py`. The legacy single-paragraph header form is removed; using it is a constitution violation.
25. `.claude/features/rabbit-cage/scripts/build.py` exists and is executable; reads `build-contract.json` and builds all declared targets.
26. `.claude/features/rabbit-cage/test/test-generated-surface.py` exists and exits 0 on a clean workspace (all check_on_stop copy-file targets match their sources).
27. `generate-skills-dir.py` does NOT exist in `.claude/features/rabbit-cage/scripts/` (deleted; superseded by build.py + build-contract.json).
28. `test-symlinks.sh` does NOT exist in `.claude/features/rabbit-cage/test/` (deleted; superseded by test-generated-surface.py).
29. `surface.hooks`, `surface.commands`, and `surface.settings` in `feature.json` are all `[]` (empty arrays); hooks, commands, and settings are now managed via build-contract.json copy-file targets.
30. `build.py` passes `RABBIT_ROOT=<repo_root>` as an environment variable when invoking `generate-claude-md.py` for `generate-claude-md` targets, so that installs into non-git directories (e.g., temp dirs during `install.sh`) succeed without `git rev-parse` errors.
39. Every runtime script under `.claude/features/rabbit-cage/hooks/` and `.claude/features/rabbit-cage/scripts/` is a standalone executable Python file (`#!/usr/bin/env python3`). No `.sh` files exist under either directory. `install.py` at the rabbit-cage root is the bootstrap installer (also Python). Tests under `.claude/features/rabbit-cage/test/` are also Python (`.py`); no `.sh` test files exist in rabbit-cage.
40. The Python runtime scripts in rabbit-cage are: in `hooks/` — `refresh.py`, `scope-guard.py`, `session-init.py`, `sync-check.py`; in `scripts/` — `build.py`, `build-targets.py`, `generate-claude-md.py`, `generate-claude-md-header.py`, `new-feature.py`, `rabbit-project.py`, `rabbit-project-consolidate.py`, `rabbit-project-map.py`, `rabbit-project-set-path.py`, `scope-guard-on.py`, `validate-all.py`, `workspace-tree.py`. Each preserves the stdin/stdout/exit-code contract of the `.sh` predecessor it replaces.

## Team-wide Permissions

`.claude/features/rabbit-cage/settings.json` (the canonical source for the build-managed
copy at `.claude/settings.json`) declares a `permissions` block holding **team-wide
defaults** that ship with the repo. These defaults apply to every checkout without
per-user configuration.

The current team-wide defaults are:

- **allow**: `Bash(*)`, `Write`, `Edit` — every bash command, file-write tool, and
  file-edit tool runs without prompting. `Write` and `Edit` are scope-guarded at the
  hook layer (see "Scope-Guard Override" below); allowing them at the permission
  layer means the scope-guard hook is the single decision point for write
  authorization, not Claude Code's permission-prompt UI.
- **deny**: `Bash(git merge *)`, `Bash(git push * main)`, `Bash(git push origin main)` —
  blocks direct merges (target branch cannot be inferred from the command string, so
  all direct merges are blocked) and pushes to `main`. Deny rules take precedence over
  allow rules in Claude Code's permission evaluation.

Team-wide permissions live in the **source** file (not the build-managed destination)
so that `build.py`'s `copy-file` regeneration propagates them on every drift rebuild.
Writing the same block directly to `.claude/settings.json` (the destination) would be
destroyed by the next surface rebuild — Inv 50.

Personal overrides continue to live in `.claude/settings.local.json` (gitignored) and
are managed via `/rabbit-config bash-allow` / `/rabbit-config allowed-tools`. Claude
Code merges permission arrays across all sources, so personal entries add to (rather
than replace) the team-wide defaults.

**Bypass mode (Inv 69).** Bypass mode is a per-user preference, not a team-wide
default. The shared `settings.json` MUST NOT declare `permissions.defaultMode`;
operators who want native per-write prompts suppressed (so the scope-guard
PreToolUse hook becomes the single decision point for write authorization)
opt in by writing `permissions.defaultMode = "bypassPermissions"` to their
own user-local `.claude/settings.local.json` via `/rabbit-config
bypass-permissions true`. The companion knob `skipDangerousModePermissionPrompt`
(suppresses the one-time bypass-mode startup warning) is likewise per-user and
lives in `.claude/settings.local.json`. Neither key MAY appear in the shared
`settings.json` source.

### Invariants

51. `.claude/features/rabbit-cage/settings.json` declares a top-level `permissions`
    object whose `allow` array contains exactly the entries `Bash(*)`, `Write`,
    and `Edit` (in that order), and whose `deny` array contains exactly the entries
    `Bash(git merge *)`, `Bash(git push * main)`, and `Bash(git push origin main)`.
    The build-managed copy at `.claude/settings.json` holds the same `permissions`
    block by virtue of being a `copy-file` target of the source. No other top-level
    keys (`env`, `hooks`) are altered by this invariant. `Write` and `Edit` at the
    permission layer move all write authorization to the scope-guard hook, which is
    the single decision point for whether a write is allowed.

## /rabbit-config Skill

`/rabbit-config` is the extensible configuration skill for the rabbit workflow. It uses a subcommand pattern to group configuration operations under one entry point.

The skill source lives at `.claude/features/rabbit-cage/skills/rabbit-config/`:

- `SKILL.md` — the skill manifest. The frontmatter `description` documents when dispatchers should invoke the skill (config changes for prompt threshold, tool permissions, human-approval bypass, etc.). The body enumerates every subcommand and its CLI surface so the dispatcher can read the full interface without opening the script.
- `scripts/rabbit-config.py` — the implementation. A standalone Python 3 script (stdlib only) parsing argv and dispatching to one subcommand handler per call.

There is NO slash-command file for `/rabbit-config`. The skill is the sole interface. Dispatchers (and Claude on behalf of the user) invoke it as `Skill("rabbit-config", args: "<subcommand> [args...]")`, which executes the skill script. Keeping a parallel slash-command file would duplicate the entry in the Claude Code skill list and create two confusable surfaces for the same functionality.

**Syntax (skill invocation):** `Skill("rabbit-config", args: "<subcommand> [args...]")`

**Subcommands:** `prompt-threshold`, `allowed-tools`, `bash-allow`, `permissions`, `human-approval`, `bypass-permissions`. Each is documented below.

### Subcommand: prompt-threshold

Sets or restores the auto-refresh threshold (number of prompts between policy re-injections).

- `/rabbit-config prompt-threshold <N>` — writes `RABBIT_REFRESH_EVERY=N` to `.claude/settings.local.json`. `N` must be a positive integer. Takes effect on the next session start.
- `/rabbit-config prompt-threshold` (no value) — removes the `RABBIT_REFRESH_EVERY` key from `.claude/settings.local.json`, restoring the default value defined in `.claude/settings.json`.

### Subcommand: allowed-tools

Manages entries in `permissions.allow` of `.claude/settings.local.json`. Operators use this to register Claude Code tool names (e.g. `Edit`, `Write`, `WebFetch`) that should always be permitted without a runtime prompt.

- `/rabbit-config allowed-tools add <tool>` — adds `<tool>` to `permissions.allow` in `.claude/settings.local.json`. No-op if the entry is already present (idempotent). `<tool>` must be a non-empty string. Takes effect on the next session start.
- `/rabbit-config allowed-tools remove <tool>` — removes `<tool>` from `permissions.allow`. No-op if the entry is absent.
- `/rabbit-config allowed-tools` (no action) — lists the current entries in `permissions.allow`, one per line, in array order.

Bash-rule entries (strings of the form `Bash(<command>:*)`) are managed by the `bash-allow` subcommand and are not affected by `allowed-tools`. The `allowed-tools` subcommand operates only on entries that do NOT match the `Bash(...)` pattern; `add`/`remove` reject inputs that begin with `Bash(` so the two subcommands stay in their own lanes.

### Subcommand: bash-allow

Manages bash-command allowlist entries (e.g. `touch`, `cat`, `echo`, `ls`, `python`) in `permissions.allow` of `.claude/settings.local.json`. Each entry is stored as a string of the form `Bash(<command>:*)` so Claude Code matches it against the configured command verb.

- `/rabbit-config bash-allow add <command>` — adds the entry `Bash(<command>:*)` to `permissions.allow` in `.claude/settings.local.json`. No-op if the entry is already present (idempotent). `<command>` must be a non-empty string composed of characters that do not include `(`, `)`, `:`, or whitespace. Takes effect on the next session start.
- `/rabbit-config bash-allow remove <command>` — removes the entry `Bash(<command>:*)` from `permissions.allow`. No-op if the entry is absent.
- `/rabbit-config bash-allow` (no action) — lists the current bash-allow entries, one `<command>` per line, in array order.

### Subcommand: permissions

Manages owner write permission on `archive/` and `test/` directories by delegating to `.claude/features/rabbit-cage/scripts/repo-permissions.py`. Used after `git clone` to lock or before editing to unlock.

- `/rabbit-config permissions lock` — strips owner write bit from `archive/` and `test/` so the worktree resists accidental edits.
- `/rabbit-config permissions unlock` — restores owner write to those directories before authoring edits.

### Subcommand: human-approval

Manages the Step 4 (HUMAN-APPROVAL) gate state via the marker file `.rabbit-human-approval-bypass` at the repo root. The marker is gitignored. The subcommand takes a boolean value following contract Inv 15 (boolean CLI values use `true`/`false`):

- `/rabbit-config human-approval true` — deletes `.rabbit-human-approval-bypass`. The Step 4 gate is ACTIVE: `rabbit-feature-touch` dispatchers wait for explicit in-conversation user approval. This is the default posture for a fresh checkout.
- `/rabbit-config human-approval false` — writes `.rabbit-human-approval-bypass` at the repo root with content `session`. The Step 4 gate is BYPASSED: every subsequent `rabbit-feature-touch` dispatch passes `--human-approval-gate false` to `dispatch-tdd-subagent.py` and skips the in-conversation wait. Use ONLY after explicit user authorization.
- `/rabbit-config human-approval` (no action) — prints the current state to stdout: either `true` (marker absent, gate active) or `false` (marker present, gate bypassed). No file is modified.

`sync-check.py` emits a red `[rabbit]` `systemMessage` on every Stop event while `.rabbit-human-approval-bypass` is present, so the bypass cannot be silently forgotten:
`[rabbit] HUMAN APPROVAL BYPASS ACTIVE — Step 4 skipped for all rabbit-feature-touch dispatches.`

The marker stays in place across sessions until explicitly revoked via `/rabbit-config human-approval true` or manual deletion. It is a hard state, not conversation memory — the dispatcher reads the file at every dispatch, not Claude's recollection of prior approval.

### Subcommand: bypass-permissions

Manages the per-user `permissions.defaultMode = "bypassPermissions"` key in `.claude/settings.local.json`. Bypass mode tells Claude Code to skip its native per-write permission prompts so the scope-guard PreToolUse hook becomes the single decision point for write authorization. Because different operators may want different behavior, this is a per-user opt-in — it lives in `settings.local.json` (gitignored), never in the shared `settings.json`. The subcommand takes a boolean value following contract Inv 15 (boolean CLI values use `true`/`false`):

- `/rabbit-config bypass-permissions true` — writes `{"permissions": {"defaultMode": "bypassPermissions"}}` merged into `.claude/settings.local.json`. Idempotent: re-invoking when the key already holds `"bypassPermissions"` is a no-op (exit 0) with a confirmation line. Takes effect on the next session start.
- `/rabbit-config bypass-permissions false` — removes the `permissions.defaultMode` key from `.claude/settings.local.json`. If `permissions` becomes `{}` it is removed; if the resulting `settings.local.json` is `{}` the file is left as an empty object (not deleted). Idempotent: invoking when the key is absent is a no-op (exit 0). Takes effect on the next session start.
- `/rabbit-config bypass-permissions` (no action) — prints exactly one line to stdout: `true` if `.claude/settings.local.json` declares `permissions.defaultMode = "bypassPermissions"`, otherwise `false`. No file is modified.

**Common rules for permission subcommands (`allowed-tools`, `bash-allow`):**

- The target file is `.claude/settings.local.json` (not `.claude/settings.json`). `settings.local.json` is outside the build system's copy-file target set, so permissions persist across `sync-check.py` surface-drift rebuilds. Writes to `settings.local.json` are unconditionally permitted by the scope-guard filename allowlist.
- If `permissions` or `permissions.allow` is missing from `settings.local.json`, `add` creates it as needed. `remove` on a missing key is a no-op (exit 0).
- After removal, if `permissions.allow` becomes empty, the key remains as an empty array (it is not deleted); if `permissions` itself becomes the only key and is `{"allow": []}`, it is left in place. The shape of `settings.local.json` other than the `permissions.allow` array is never modified by these subcommands.
- Output of `add` and `remove` is a single confirmation line on stdout (e.g. `Added Bash(touch:*) to .claude/settings.local.json`); no output if the operation was a no-op other than `Already present` / `Not present`.
- List operations (no-action form of `allowed-tools` and `bash-allow`) read from `.claude/settings.local.json` only. The canonical surface source `.claude/features/rabbit-cage/settings.json` MAY declare a `permissions` block holding team-wide defaults (see "Team-wide Permissions" below); `.claude/settings.json` is its build-managed copy. Claude Code merges permission arrays across all settings sources (user → project → local), so team-wide defaults from `settings.json` and personal entries from `settings.local.json` compose. Neither `settings.json` nor its source is consulted by list operations — list operations remain scoped to personal `settings.local.json` entries.

**Error handling:** unknown subcommands produce a usage message listing available subcommands. An invalid value (non-positive-integer) for `prompt-threshold`, an empty `<tool>`/`<command>`, an invalid `<command>` for `bash-allow` (containing `(`, `)`, `:`, or whitespace), an unknown action for `allowed-tools` or `bash-allow` (anything other than `add`, `remove`, or no action), or a `Bash(...)`-shaped value passed to `allowed-tools add`/`remove` all produce an error and exit non-zero without modifying any file.

**Replaces:** `/rabbit-set-threshold` — that command is removed; `prompt-threshold` is its direct functional replacement. The subcommand pattern makes it straightforward to add future configuration subcommands (e.g., `/rabbit-config set-something-else [value]`).

### Invariants

25. The slash-command file `.claude/features/rabbit-cage/commands/rabbit-config.md` does NOT exist. `/rabbit-config` is invoked exclusively through the `rabbit-config` skill at `.claude/features/rabbit-cage/skills/rabbit-config/`. Keeping a parallel command file would surface a duplicate entry in the Claude Code skill list (the command file's frontmatter `description` is treated as a skill advertisement) and create two confusable interfaces for the same functionality. The deleted command file MUST NOT be recreated; any new entry point goes through the skill's SKILL.md.
26. `/rabbit-set-threshold` command file does NOT exist anywhere in the repository.
27. `/rabbit-config prompt-threshold <N>` writes `{"env": {"RABBIT_REFRESH_EVERY": "<N>"}}` merged into `.claude/settings.local.json`.
28. `/rabbit-config prompt-threshold` (no argument) removes the `RABBIT_REFRESH_EVERY` key from the `env` object in `.claude/settings.local.json`; if `env` becomes empty the key is also removed.
29. An unknown subcommand to `/rabbit-config` emits a usage message and exits non-zero without modifying any file.
43. `/rabbit-config allowed-tools add <tool>` adds `<tool>` to the `permissions.allow` array in `.claude/settings.local.json`, creating the `permissions` and `permissions.allow` keys if they do not exist; the operation is idempotent (already-present entries are not duplicated).
44. `/rabbit-config allowed-tools remove <tool>` removes `<tool>` from `permissions.allow` in `.claude/settings.local.json`; absence of the entry is a no-op (exit 0). The `permissions.allow` key is left as an empty array when emptied; it is not deleted.
45. `/rabbit-config bash-allow add <command>` adds the literal string `Bash(<command>:*)` to `permissions.allow` in `.claude/settings.local.json`; idempotent.
46. `/rabbit-config bash-allow remove <command>` removes the literal string `Bash(<command>:*)` from `permissions.allow` in `.claude/settings.local.json`; absence is a no-op (exit 0).
47. `/rabbit-config allowed-tools` (no action) and `/rabbit-config bash-allow` (no action) print current entries one per line to stdout from `.claude/settings.local.json` and exit 0; they do not modify any file. `bash-allow` lists prints only the inner `<command>` (with `Bash(` and `:*)` stripped) and skips entries that do not match the `Bash(<command>:*)` shape.
48. `/rabbit-config allowed-tools add <tool>` and `/rabbit-config allowed-tools remove <tool>` reject inputs whose value begins with `Bash(` and exit non-zero with an error directing the operator to use `bash-allow` instead.
49. `/rabbit-config bash-allow add <command>` rejects `<command>` values containing any of `(`, `)`, `:`, or whitespace, and exits non-zero without modifying any file.
50. The permission subcommands (`allowed-tools`, `bash-allow`) write to `.claude/settings.local.json` (which is on the scope-guard filename allowlist); they never write to `.claude/settings.json`. This isolates permission grants from the build system: `.claude/settings.json` is a copy-file target regenerated by `build.py` on surface drift (see `build-contract.json`), which would silently destroy any `permissions` block written there. `.claude/settings.local.json` is outside the build system's copy-file target set and persists across surface-drift rebuilds.
53. `.claude/features/rabbit-cage/skills/rabbit-config/SKILL.md` exists. Its YAML frontmatter declares `name: rabbit-config` and a `description` field that names all six subcommands (`prompt-threshold`, `allowed-tools`, `bash-allow`, `permissions`, `human-approval`, `bypass-permissions`) so the dispatcher can decide to invoke it. Its body enumerates the full CLI for every subcommand verbatim — no opening the script needed to read the interface.
54. `.claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py` exists, is executable (`chmod +x`), and is the sole implementation of `/rabbit-config`. It is a standalone Python 3 script using stdlib only. There is no slash-command file; invocation goes through the skill entry only.
55. `/rabbit-config human-approval false` writes the file `.rabbit-human-approval-bypass` at the repo root with content `session` and prints a single confirmation line. Idempotent: re-invoking when the marker already exists is a no-op exit 0 with the same confirmation. The legacy verbs `bypass` and `gated` are removed; only `true` and `false` are accepted (per contract Inv 15).
56. `/rabbit-config human-approval true` deletes `.rabbit-human-approval-bypass` from the repo root and prints a single confirmation line. Idempotent: invoking when the marker is absent is a no-op exit 0.
57. `/rabbit-config human-approval` (no action) prints exactly one line to stdout: `false` if `.rabbit-human-approval-bypass` exists at repo root, otherwise `true`. No file is modified. Exits 0.
58. `.rabbit-human-approval-bypass` is gitignored (appears in `.gitignore`). The marker is a runtime artifact, never committed.
59. `sync-check.py` emits a red `[rabbit]` `systemMessage` on every Stop event while `.rabbit-human-approval-bypass` exists at the repo root: `[rabbit] HUMAN APPROVAL BYPASS ACTIVE — Step 4 skipped for all rabbit-feature-touch dispatches`. The marker is NOT consumed by `sync-check.py` — it persists across Stops until explicitly removed via `/rabbit-config human-approval true`. This human-approval-bypass alert sits between scope-guard-off and skills-updated in the conditional-priority order (see Inv 37).
60. `permissions [lock|unlock]` is a `/rabbit-config` subcommand that shells out to `.claude/features/rabbit-cage/scripts/repo-permissions.py` with the same action. Unknown actions exit non-zero with a usage message; no other file is modified.
61. `session-init.py` MUST implement the R1 branch enforcement behavior described in Invariants 21-23 exactly. On `SessionStart`, it MUST run `git branch --show-current`; if the result is `main` or `master`, it MUST run `git checkout -b session/<YYYYMMDD-HHMMSS>` (timestamp from `date +%Y%m%d-%H%M%S`) and emit a green `[rabbit]` systemMessage naming the created branch. The implementation MUST be present and active in the deployed hook; a documented-only or no-op implementation is a constitution violation. Tests MUST exercise the on-main path (assert branch created and message emitted) and the off-main path (assert no-op).
62. `sync-check.py` surface-drift alert MUST be RED (`\x1b[31m`), consistent with Inv 18's color convention (alert/error messages are red). A GREEN surface-drift alert violates the convention and silently downgrades the visibility of a real drift condition.
63. `sync-check.py` drift-detected path emits `additionalContext` to surface the CLAUDE.md policy block. The first-run path (CLAUDE.md not existing on disk) was REMOVED in BACKLOG-19 — in any real checkout CLAUDE.md is committed and the path was dead code. The `additionalContext` value MUST be either (a) the fully-expanded policy content with `@`-imports resolved, OR (b) accompanied by a clear in-message note that the agent must independently load the referenced policy files. Emitting raw unexpanded `@<path>` import lines as `additionalContext` without expansion AND without a note is a silent failure: the policy is not re-injected because Claude Code does not follow `@`-imports inside `additionalContext` strings.
64. rabbit-cage tests MUST NOT mutate live source files in `.claude/features/rabbit-cage/` (including `settings.json`, `settings.local.json`, `feature.json`, and any committed source file) without restoring them on test exit. Tests that need to write to these paths MUST do so inside an isolated temporary directory (e.g., via `tempfile.mkdtemp` + a clean repo copy) so that test interruption, crash, or parallel execution cannot leave the working tree in a corrupted state.
65. `scope-guard.py` MUST DENY (exit 2) writes when an active scope marker `.rabbit-scope-active` or `.rabbit-scope-active-<feature>` names a feature that `find-feature.py` cannot resolve to a real feature path (i.e., `find_feature_path` returns None). The current silent-ALLOW behavior on unresolvable markers defeats the scope-guard's default-deny posture: a typo'd or malicious marker bypasses the entire write gate. The DENY message MUST name the unresolvable feature and direct the user to verify the marker name.
66. `new-feature.py` MUST scaffold `test/run.py` (Python-only stack per Inv 39), not `test/run.sh`. The scaffolded `feature.json` MUST include `template_version` matching the current contract template version. A scaffolded feature MUST pass `validate-feature.py` immediately with no manual fixups.
67. `commands/rabbit-project.md` MUST reference only Python scripts that exist (under `.claude/features/rabbit-cage/scripts/`), never `.sh` scripts or stale relocated paths. Any `.sh` reference is a constitution violation per Inv 39.
68. `rabbit-config.py human-approval false` confirmation message MUST be self-explanatory and consistent with the gate semantics. The output MUST state both the new marker state and the practical effect, e.g., `Human-approval gate BYPASSED. Marker .rabbit-human-approval-bypass written. Step 4 will be skipped for all dispatches until you run /rabbit-config human-approval true.` Conversely `true` MUST say `Human-approval gate ENABLED. Marker .rabbit-human-approval-bypass removed. Step 4 will wait for in-conversation approval on each dispatch.` Avoid bare adjectives like `DISABLED` that read ambiguously against the gate vs the marker.
69. Bypass mode is a per-user preference. The shared
    `.claude/features/rabbit-cage/settings.json` source and its build copy
    `.claude/settings.json` MUST NOT declare `permissions.defaultMode`.
    Operators who want native per-write prompts suppressed opt in by
    writing `permissions.defaultMode = "bypassPermissions"` to their own
    `.claude/settings.local.json` via `/rabbit-config bypass-permissions
    true`. The companion key `skipDangerousModePermissionPrompt` is
    likewise a per-user preference and MUST live in
    `.claude/settings.local.json` only; neither key MAY appear in the
    shared `settings.json` source.
70. Hooks `sync-check.py` and `session-init.py` MUST log unexpected
    exceptions to stderr via a `_log_exc()` helper rather than silently
    swallowing them with bare `except Exception: pass`. The happy-path
    contract (exit 0 with no stderr noise) is preserved on successful runs;
    only the error-handler arms gain visibility. A silently-failing hook is
    indistinguishable from a missing one and effectively disables policy
    enforcement, so the silent-swallow anti-pattern is forbidden in these
    hooks (BACKLOG-17). The remaining hooks (`scope-guard.py`, `refresh.py`)
    are eligible for the same treatment in a follow-up but are NOT covered
    by this invariant — extending them is out-of-scope here because their
    failure modes are narrower (pure-function helpers, no subprocess
    invocations beyond the optional `git rev-parse`).
71. `/rabbit-config bypass-permissions true` writes
    `{"permissions": {"defaultMode": "bypassPermissions"}}` merged into
    `.claude/settings.local.json`, creating the `permissions` key if it
    does not exist. Idempotent: a second invocation while the key already
    equals `"bypassPermissions"` is a no-op (exit 0) and does not rewrite
    the file. The target file is `.claude/settings.local.json` only; the
    shared `.claude/settings.json` MUST NOT be modified.
72. `/rabbit-config bypass-permissions false` removes the
    `permissions.defaultMode` key from `.claude/settings.local.json`. If
    `permissions` becomes empty (`{}`) after removal, the `permissions`
    key is also removed. Idempotent: invoking when the key is already
    absent is a no-op (exit 0). Other keys inside `permissions` (e.g.,
    `allow`, `skipDangerousModePermissionPrompt`) are left untouched.
73. `/rabbit-config bypass-permissions` (no action) prints exactly one
    line to stdout: `true` if `.claude/settings.local.json` declares
    `permissions.defaultMode == "bypassPermissions"`, otherwise `false`.
    No file is modified. Exits 0. An invalid value (anything other than
    `true`, `false`, or no action) exits non-zero with an error message
    and modifies no file.
74. Confirmation output for `/rabbit-config bypass-permissions true|false`
    follows the same self-explanatory pattern as `human-approval` (Inv 68):
    `true` MUST say `Bypass permissions ENABLED in .claude/settings.local.json.
    Claude Code will skip native per-write prompts on next session start.`
    and `false` MUST say `Bypass permissions DISABLED. permissions.defaultMode
    removed from .claude/settings.local.json. Claude Code will prompt for
    writes again on next session start.` Idempotent invocations MUST state
    that the file was not rewritten.

## Out of Scope

- Content authored by other features — rabbit-cage wires their surface, not their content.
- `settings.local.json` — user-local overrides; never written by rabbit-cage except via the `/rabbit-config` command on explicit user request.
- Scripts: rabbit-cage owns no runtime scripts beyond `install.py` and those registered in its contract.
- Workspace hierarchy display — owned and wired by the `rabbit-workspace-map` skill in the contract feature; rabbit-cage no longer declares it in its `feature.json` skills list.

## Tech Stack

Python 3 is the sole runtime scripting language for rabbit-cage. Every
runtime script under `hooks/` and `scripts/` is a standalone executable
Python file (`#!/usr/bin/env python3`) with the same stdin/stdout/exit-code
contract as the `.sh` predecessor it replaces. Bash is not a runtime
dependency for any rabbit-cage hook or script.

**Bootstrap installer — `install.py`:** the rabbit-cage installer is a
standalone Python 3 script (`#!/usr/bin/env python3`, stdlib only). It is
the bootstrap entry point invoked by operators on a fresh checkout.
No `.sh` files remain in rabbit-cage.

**Tests are Python.** Tests under `.claude/features/rabbit-cage/test/` are `.py`
files; no `.sh` test files exist in rabbit-cage. The migration to Python is
complete for both runtime scripts and test harnesses.

## Scope-Guard Override

A human-approved override mechanism allows the scope-guard to permit a write
that would otherwise be denied. The override is granted by the human creating
a marker file at the repo root; the act of running the command IS the
approval.

**Marker files (both gitignored, repo-root):**

- `.rabbit-scope-override` — contents are exactly `one-time` or `session`.
  Created by the human (e.g. `echo one-time > .rabbit-scope-override`).
- `.rabbit-scope-override-used` — created by `scope-guard.py` when a
  `one-time` override is consumed. Acts as a single-shot post-event signal
  for `sync-check.py` to surface the consumption.

**`scope-guard.py` semantics** (evaluated before the default-deny step):

- `.rabbit-scope-override` = `session` → ALLOW; marker is left in place so
  the guard remains down for the rest of the session.
- `.rabbit-scope-override` = `one-time` → ALLOW; `scope-guard.py` DELETES
  `.rabbit-scope-override` and CREATES `.rabbit-scope-override-used`.
- Absent or other content → fall through to the default-deny path.

**`sync-check.py` semantics** (Stop hook, after the normal drift check):

- `.rabbit-scope-override` = `session` → emit a red `[rabbit]` systemMessage
  on every Stop, signalling that the guard is **currently off**:
  `[rabbit] SCOPE GUARD OFF (session override active)`
- `.rabbit-scope-override-used` exists → emit a **distinct** red `[rabbit]`
  systemMessage once, signalling that the guard was bypassed once and is now
  re-armed, then DELETE `.rabbit-scope-override-used`:
  `[rabbit] SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed)`

**Confirm-token approval flow:** when scope-guard blocks a write, the main
session surfaces an explicit confirm token to the user in-conversation,
asking whether to grant a one-time or session override. The token asks one
binary question (one-time or session). Upon explicit in-conversation user
approval, the main session writes `.rabbit-scope-override` itself with the
approved mode (`one-time` or `session`), then proceeds with the write.
`scope-guard.py` never creates `.rabbit-scope-override`; it only reads
and (for `one-time`) deletes it.

**Revoking a session override (scope guard back on):** A session override
stays in place until explicitly revoked. To revoke it, run:

    .claude/features/rabbit-cage/scripts/scope-guard-on.py

`scope-guard-on.py` deletes `.rabbit-scope-override` (if present) and
emits a confirmation message. After revocation the guard returns to its
default-deny posture immediately — no session restart is required. The
script is a no-op if no override is active.

**Filename allowlist:** `scope-guard.py` maintains a filename allowlist that
always permits writes regardless of scope-marker state. The allowlisted
basenames are: `settings.local.json`, `.gitignore`, and
`.rabbit-scope-override`. The `.rabbit-scope-override` entry is required so
that the confirm-token approval flow is not a catch-22: Claude must be able to
write the override file after receiving user approval, even when no scope
marker is active.

`settings.json` is NOT on the basename allowlist. The repo-root
`.claude/settings.json` is owned by rabbit-cage and is the canonical Claude
Code config (permissions, hooks, env); changes to it must follow the
rabbit-cage scope discipline like any other rabbit-cage file. Permitting
blanket writes via a basename allowlist would let any agent silently edit
Claude Code permissions without going through `rabbit-feature-touch`.

**Path-prefix allowlist:** `scope-guard.py` additionally permits writes to
specific repo-root path prefixes regardless of scope-marker state. The
allowlisted prefixes are: `.claude/bugs/`, `.claude/backlogs/`, and `.rabbit/`.
The `.rabbit/` prefix is required because the `rabbit-feature-touch` protocol
routinely writes `.rabbit/impl-suggestion-<feature>.json` (Step 3, via
`rabbit-spec`) and `.rabbit/tdd-report-<feature>.json` (Step 8, via the TDD
subagent) as part of normal feature work. These writes are dispatcher
metadata, not feature code, and must not require a session override —
override semantics are reserved for exceptional human-approved bypasses, not
routine workflow writes.

For each allowlisted prefix, the match accepts BOTH the exact directory path
(e.g., `.rabbit`) AND any path inside it (e.g., `.rabbit/foo.json`). The
exact-directory form is required so that directory-creation operations like
`mkdir .rabbit` (where the Bash target is `.rabbit` with no trailing slash)
are permitted; without it, only writes to files inside an already-existing
directory would match. The exact form is a strict equality check on the
directory path itself, never a prefix — this prevents accidental matches on
sibling paths like `.rabbit-scope-active` or `.rabbit-human-approval-bypass`.

**Path-pattern allowlist:** `scope-guard.py` additionally permits writes to
the path pattern `.claude/features/<feature>/docs/spec/spec.md` regardless
of scope-marker state, where `<feature>` is any single path segment
(matched as `[^/]+`). This permits the `rabbit-feature-touch` Step 3
spec-authoring step — which invokes `rabbit-spec` from the main session
before any per-feature scope marker is set by the TDD subagent — to update
the spec without requiring a manual one-time override. The pattern is
narrowly scoped to the `docs/spec/spec.md` file only; other files under
`.claude/features/<feature>/docs/` remain governed by the default scope
rules.

## Invariants (additional)

11. `.rabbit-scope-override` and `.rabbit-scope-override-used` are gitignored.
20. `scope-guard.py` filename allowlist contains exactly: `settings.local.json`,
    `.gitignore`, and `.rabbit-scope-override`. Writes to any of these
    basenames are always permitted, regardless of scope-marker state. This
    allowlist must include `.rabbit-scope-override` to enable the
    confirm-token approval flow (Claude writes the override file after
    in-conversation user approval without a scope marker active).
    `settings.json` is NOT on this allowlist: `.claude/settings.json` is
    owned by rabbit-cage (canonical Claude Code config — permissions, hooks,
    env) and writes to it must require an active rabbit-cage scope marker
    like any other rabbit-cage file. A basename allowlist for `settings.json`
    would let agents silently edit Claude Code permissions without going
    through `rabbit-feature-touch`.
    Additionally, `scope-guard.py` maintains a path-prefix allowlist that
    permits writes anywhere under the following repo-root prefixes regardless
    of scope-marker state: `.claude/bugs/`, `.claude/backlogs/`, and
    `.rabbit/`. The `.rabbit/` prefix is required so that the
    `rabbit-feature-touch` dispatcher can write `.rabbit/impl-suggestion-<feature>.json`
    and `.rabbit/tdd-report-<feature>.json` during normal feature work without
    needing a session override (override is reserved for exceptional
    human-approved bypasses, not routine workflow writes). For each
    allowlisted prefix, the match permits BOTH the exact directory path
    (e.g., `abs_path == REPO_ROOT + "/.rabbit"`) AND any path inside it
    (e.g., `abs_path.startswith(REPO_ROOT + "/.rabbit/")`). The exact form
    is required for directory-creation operations like `mkdir .rabbit` whose
    Bash target is `.rabbit` with no trailing slash; the exact form is a
    strict equality check, never a prefix, so sibling paths such as
    `.rabbit-scope-active` and `.rabbit-human-approval-bypass` do NOT match.
    `scope-guard.py` also maintains a path-pattern allowlist permitting
    writes to `.claude/features/<feature>/docs/spec/spec.md` for any single
    path segment `<feature>` (matched as `[^/]+`), regardless of
    scope-marker state. This pattern is required so that
    `rabbit-feature-touch` Step 3 spec-authoring (which runs in the main
    session before any per-feature scope marker is set) can update the spec
    via `rabbit-spec` without a manual override. The pattern is narrowly
    scoped to `docs/spec/spec.md`; other files under `.claude/features/<feature>/docs/`
    remain governed by the default scope rules.
12. `scope-guard.py` never creates `.rabbit-scope-override`; it only reads it
    and (for `one-time`) deletes it after consumption. The main session (Claude)
    may write `.rabbit-scope-override` after receiving explicit in-conversation
    user approval via the confirm-token flow.
52. When `scope-guard.py` reaches the default-deny path (no scope marker, no
    override, no allowlist match), the DENY message printed to stderr MUST
    present three explicit options in a structured form, in this order:
    (1) SESSION OVERRIDE — bypasses scope-guard for the entire session;
        requires explicit in-conversation user confirmation before writing
        `.rabbit-scope-override` with content `session`.
    (2) ONE-TIME OVERRIDE — bypasses scope-guard for a single write only;
        requires explicit in-conversation user confirmation before writing
        `.rabbit-scope-override` with content `one-time`.
    (3) USE rabbit-feature-touch (recommended) — the correct governed path
        for feature edits; invokes TDD cycle, advances `tdd_state`, creates
        a PR; no override needed.
    The message MUST explicitly state that both override options require
    in-conversation user confirmation and MUST NOT be written speculatively.
    The terse "Dispatcher must touch .rabbit-scope-active before calling Agent"
    instruction is removed — it framed the override as a procedural step,
    which is the rationalization pattern that BUG-1 captured. The new
    structured form forces a decision point: pick one of three explicit
    paths, none of which is silent compliance.
13. A `one-time` override consumed by `scope-guard.py` is acknowledged exactly
    once by `sync-check.py`, after which `.rabbit-scope-override-used` is
    removed.
41. `scope-guard-on.py` exists at `.claude/features/rabbit-cage/scripts/scope-guard-on.py`
    and is executable. It deletes `.rabbit-scope-override` (if present) and prints a
    confirmation to stdout. It is a no-op if no override file exists. It is the
    canonical answer to "scope guard back on" / "revoke the session override".
42. The double-quoted region stripping `re.sub` in `extract_bash_targets()` of
    `scope-guard.py` uses the `re.DOTALL` flag so that multi-line double-quoted
    strings (e.g., from backslash-newline continuations) are fully removed before
    pattern matching, preventing false-positive DENY on content inside the string.
    Additionally, the entire quote-stripping pass runs on the FULL command
    string BEFORE splitting on `;|&` segment delimiters (not per-segment
    after splitting). This ensures that `;|&` characters inside quoted
    argument values (e.g., a `--description "..."` text containing
    semicolons or pipes) are stripped along with the rest of the quoted
    content, preventing spurious segment boundaries that would leave
    residual unbalanced-quote segments and cause false-positive DENY on
    write-pattern characters (`>`, `>>`, `tee`, etc.) inside the original
    quoted text.
14. `generate-skills-dir.py --check` detects drift by comparing the sha256 of
    each source `SKILL.md` directly against the sha256 of the corresponding
    copy at `.claude/skills/<name>/SKILL.md`. No external baseline file is
    used or maintained. (Note: this functionality is supplied by `build.py`
    via `build-contract.json` copy-file targets; the standalone
    `generate-skills-dir.py` does not exist — see Inv 27.)
15. `.claude/skills/` and its contents are committed to the repo;
    `.claude/skills/` does not appear in `.gitignore`.
16. `CLAUDE.md` at the repo root is committed to the repo; `CLAUDE.md` does
    not appear in `.gitignore`.
17. On every Stop event, `sync-check.py` compares the committed
    `CLAUDE.md` against a fresh regeneration from the policy source files.
    On discrepancy it regenerates `CLAUDE.md` in place and emits a red
    `[rabbit]` `systemMessage` warning that the committed copy drifted from
    the policy sources, instructing the human to commit the regenerated
    file.
18. `[🐇 rabbit 🐇]` `systemMessage` brand, decoration, color, and message
    bodies are sourced from the centralized print registry
    `.claude/features/contract/schemas/rabbit-print-messages.json` via the
    shared renderer `.claude/features/contract/scripts/rabbit_print.py`
    (CONTRACT-BACKLOG-20 / contract Inv 5, 34, 35, 36). Rabbit-cage hooks
    MUST NOT compose ANSI codes, the brand prefix, or the bar (`━━━`)
    inline; every `[🐇 rabbit 🐇]` line is the return value of one
    `rabbit_print(message_id, **kwargs)` call (banner) or one
    `rabbit_subline(text, color)` call (sub-line under a banner). The
    legacy bare `[rabbit]` prefix and any inline `\x1b[3...` escape codes
    in rabbit-cage hook source are forbidden — they are a constitution
    violation (BACKLOG-19). The color/format rule (green for info, red
    for alerts) is now encoded by the `color` field of each entry in
    `rabbit-print-messages.json`; the spec defers the per-message color
    assignment to that registry.
19. The scope guard recognizes two coexisting scope-marker formats at the
    repo root: a single global marker `.rabbit-scope-active` (contains one
    feature name; legacy / serial-dispatch form) and per-feature markers
    named `.rabbit-scope-active-<feature>` (presence alone declares scope
    for `<feature>`; designed for parallel per-feature TDD subagents that
    write to different features simultaneously without racing on a shared
    marker file). When evaluating whether a write to feature `F` is
    permitted, the scope guard treats the per-feature marker
    `.rabbit-scope-active-<F>` as authoritative for `F` and takes priority
    over the global `.rabbit-scope-active` for that named feature; the
    global marker continues to govern any feature for which no
    corresponding per-feature marker exists. Both marker formats are
    gitignored runtime artifacts; neither is ever created by rabbit-cage
    itself.

## Session-Init Branch Enforcement (R1)

`session-init.py` enforces R1 (branch-per-feature; never commit directly to main) at
session start. When the current branch is `main` or any protected branch (defined as any
branch whose name is exactly `main` or `master`), the hook automatically:

1. Creates a new branch named `session/YYYYMMDD-HHMMSS` (timestamp in local time).
2. Checks out that branch (`git checkout -b session/<timestamp>`).
3. Emits a green `[rabbit]` `systemMessage` naming the branch created, e.g.:
   `[rabbit] R1: created branch session/20260512-143000`

If the current branch is already a non-protected branch (anything other than `main` or
`master`), the hook does nothing related to branch enforcement.

**Protected branches:** `main`, `master`.

**Branch naming:** `session/YYYYMMDD-HHMMSS` using `date +%Y%m%d-%H%M%S`.

## Invariants (additional continued)

21. On `SessionStart`, `session-init.py` checks `git branch --show-current`. If the
    result is `main` or `master`, it runs `git checkout -b session/$(date +%Y%m%d-%H%M%S)`
    and emits a green `[rabbit]` systemMessage naming the new branch.
22. If the current branch is not `main` or `master`, `session-init.py` does NOT create
    or switch to any branch — the branch-enforcement block is a no-op.
23. The created branch name always begins with the prefix `session/` followed by exactly
    eight digits, a hyphen, and six digits (`session/YYYYMMDD-HHMMSS`).
24. On every Stop event, after the existing drift checks, `sync-check.py`
    detects skill updates via a self-clearing marker file:
    (a) `build-targets.py` (invoked by `build.py`) appends the skill name to
    `.rabbit-skills-updated` at the repo root ONLY when it copies a `copy-file`
    target whose destination matches `^\.claude/skills/([^/]+)/SKILL\.md$` AND
    whose content actually changed (sha256 of source differs from sha256 of
    destination, or destination does not exist). A no-op copy (identical sha256)
    does NOT write the marker and the underlying `shutil.copy2` is also skipped.
    Non-SKILL.md targets (`.claude/commands/`, `.claude/agents/`, etc.) never
    trigger the marker.
    (b) `sync-check.py` checks if `.rabbit-skills-updated` exists at the repo root.
    If it does: read the comma-joined list of skill names, delete the marker
    (self-clearing — alert fires exactly once per build), and emit a green
    `[rabbit]` `systemMessage` naming the updated skills. Exact message format:
    `[rabbit] Skills updated: <names> — will reload automatically on next invocation.`
    where `<names>` is the comma-joined skill names from the marker.
    If `.rabbit-skills-updated` is absent: silent (no output).
    No git diff is performed; the marker file IS the signal.
    (c) `session-init.py` does NOT reference `.rabbit-skills-updated`. Session-
    start clearing is unnecessary because `sync-check.py` self-clears the marker
    on first read.
    (d) The `/rabbit-refresh` command does NOT reference `.rabbit-skills-updated`
    for the same reason — the marker is consumed by `sync-check.py`.
    (e) `.rabbit-skills-updated` is gitignored.
    The skills-updated marker check participates in the aggregated emission
    described by Inv 37; its rendered line is appended to the aggregated
    `systemMessage` in priority order rather than being suppressed by a
    higher-priority condition. The single-JSON-per-invocation invariant is
    preserved: at most one JSON object is emitted per `sync-check.py`
    invocation, but that one object's `systemMessage` may carry multiple
    `[rabbit] ━━━ ... ━━━` lines.
    (f) The multi-message output strategy is **aggregation**: every pending
    condition contributes a line to the single emitted JSON object's
    `systemMessage`, ordered by priority. The Claude Code Stop hook protocol
    accepts at most one JSON object per invocation, so aggregation occurs
    INSIDE that object, not by emitting multiple objects. The priority order
    is declared in Invariant 37; the aggregation contract in Inv 38.

## Scope-Guard Quote Awareness

`extract_bash_targets()` in `scope-guard.py` is quote-aware. Before applying
any redirect or write-command pattern matching, AND before splitting the
command string on `;|&` segment delimiters, it strips single-quoted and
double-quoted regions from the FULL command string using Python's `re`
module. This prevents false positives when string data (e.g., inside
`python3 -c '...'` arguments, `--description "..."` argument values, or
heredoc bodies) contains `>`, `>>`, `;`, `|`, `&`, or command names such as
`tee`, `cp`, `mv`, or `rm`. Real unquoted redirects, separators, and write
commands are still detected correctly.

The strip-before-split order is required because if quote stripping runs
per-segment after a naive `re.split(r'[;|&]', cmd)`, then any `;|&`
character inside a quoted string causes the quoted region to be split
across multiple segments. Each resulting segment has an unbalanced quote,
so the non-greedy `'[^']*'` / `"[^"]*"` patterns cannot match the quoted
region, leaving the quoted text exposed to pattern matching as if it were
unquoted shell. This produces false-positive DENY on write-pattern
characters inside the original quoted text — for example, the substring
`<feature>).` inside a `--description "..."` value would be extracted as a
write target `).` because the unbalanced segment matches
`>>?\s*([^\s<>|&;]+)` against `<feature>).`.

The double-quoted region stripping `re.sub` call uses the `re.DOTALL` flag
(or equivalently `re.S`) so that quoted regions spanning multiple lines
(e.g., a `--description "..."` argument split across lines with
backslash-newline continuations) are fully removed before pattern matching.
Without `re.DOTALL`, `.` does not match newlines, so multi-line quoted
strings are only partially stripped, causing false-positive DENY on content
inside the string (e.g., `-> U+00F0`).

## Visual Styling

Every `systemMessage` emitted by rabbit-cage hooks (`sync-check.py`,
`session-init.py`, `refresh.py`) is wrapped in ANSI color codes
(`\x1b[32m` for green or `\x1b[31m` for red, terminated by `\x1b[0m`).
Markdown is not rendered in `systemMessage` output; ANSI escape codes are.
The color marks all `[rabbit]` messages as system-emitted (not
user-emitted), making them visually distinguishable in the Claude Code
transcript.

Color convention (binding):

- **Green (`\x1b[32m`)** — normal/info messages. Includes session-init,
  refresh, and skills-updated notifications.
- **Red (`\x1b[31m`)** — alert/error messages. Includes drift detection
  (CLAUDE.md drift, skills drift, policy drift) and scope-guard-off
  messages.

Example red alerts:

    \x1b[31m🔓 ━━━ [rabbit] SCOPE GUARD OFF (session override active) ━━━ 🔓\x1b[0m
    \x1b[31m🔓 ━━━ [rabbit] SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed) ━━━ 🔓\x1b[0m

## Runtime Artifact Naming

Runtime counter and config files use the `rabbit-` prefix (not `rbt-`).

- Prompt counter: `.rabbit-prompt-counter` (repo root, gitignored)
- Sync counter: `.rabbit-sync-counter` (repo root, gitignored)
- Prompt threshold env var: `RABBIT_REFRESH_EVERY` (default `20`, in `settings.json` and `settings.local.json`)
- Sync threshold env var: `RABBIT_SYNC_EVERY` (default `1`)

### Invariants

31. `refresh.py` reads and writes `.rabbit-prompt-counter`; reads `RABBIT_REFRESH_EVERY`.
32. `sync-check.py` reads and writes `.rabbit-sync-counter`; reads `RABBIT_SYNC_EVERY`; writes `.rabbit-prompt-counter` on the drift path; reads `RABBIT_REFRESH_EVERY` for that counter write. The first-run path was removed in BACKLOG-19.
33. `settings.json` declares env key `RABBIT_REFRESH_EVERY`; its `SessionStart` command resets `.rabbit-prompt-counter`.
34. `rabbit-refresh.md` command resets `.rabbit-prompt-counter`.
35. `workspace-tree.py` excludes `.rabbit-prompt-counter` from full listings.
36. Every runtime marker file written at the repo root MUST be listed in `.gitignore`;
    runtime markers are state, never committed source. The mandated set is:
    `.rabbit-prompt-counter`, `.rabbit-sync-counter`, `.rabbit-scope-active`,
    `.rabbit-scope-active-*`, `.rabbit-scope-override`, `.rabbit-scope-override-used`,
    `.rabbit-skills-updated`, `.rabbit-human-approval-bypass`. A repo `.gitignore` missing
    any of these is a constitution violation (BACKLOG-16): the marker would
    otherwise be commit-able and could drift between checkouts.

## sync-check.py Output Schema

`sync-check.py` emits AT MOST ONE JSON object per invocation to stdout
(Claude Code Stop hook protocol constraint). The output schema is:

```json
{
  "additionalContext": "<string — optional; only present when CLAUDE.md drift is among the pending conditions>",
  "systemMessage": "<string — newline-joined aggregation of every pending condition's ANSI-colored [rabbit] line>"
}
```

`systemMessage` is always present when JSON is emitted, and aggregates ALL
pending conditions in the priority order declared by Inv 37 — earlier-priority
lines appear first, joined by `\n`. The earlier conditional-priority strategy
(suppress all but the highest-priority condition) is REPLACED by the
aggregation strategy in RABBIT-CAGE-BACKLOG-18; a Stop event with N pending
conditions emits N `[rabbit] ━━━ ... ━━━` lines within one `systemMessage`.

`additionalContext` is present only when CLAUDE.md drift is one
of the pending conditions. Consumers (Claude Code Stop hook handler) read
`systemMessage` and optionally `additionalContext`; they never parse
free-form text.

When NO condition is pending, no JSON is emitted (exit 0, empty stdout).

## session-init.py Output Schema

`session-init.py` emits AT MOST ONE JSON object per invocation to stdout
(Inv 75). The output schema is identical in shape to `sync-check.py`'s,
with two possible pending conditions (R1 branch enforcement and policy
injection). When both apply, their `[rabbit]` lines are joined by `\n` in
`systemMessage`, R1 first, policy second; `additionalContext` carries the
policy text alongside.

### Invariants

37. `sync-check.py` uses the **aggregation** multi-message strategy
    (RABBIT-CAGE-BACKLOG-18): every pending condition emits within a single
    JSON object per Stop invocation. No condition is suppressed by a
    higher-priority condition — the priority order controls ORDERING within
    the aggregated `systemMessage`, not whether each condition appears.
    The explicit priority order (highest to lowest, used for line ordering
    within the aggregated message):
    1. CLAUDE.md drift (regenerated from policy sources)
    2. Surface drift (copy-file targets out of sync with sources)
    3. Scope-guard-off (session override active or one-time override consumed)
    4. Human-approval-bypass active (`.rabbit-human-approval-bypass` marker present at repo root)
    5. Skills-updated (`.rabbit-skills-updated` marker present)
    The Claude Code Stop hook protocol accepts at most one JSON object per
    invocation, so aggregation MUST occur inside that single JSON object:
    its `systemMessage` is the newline-joined concatenation of each pending
    condition's rendered `[rabbit] ━━━ ... ━━━` line, ordered by the
    priority list above. Conditions whose marker is consumed-on-read (e.g.
    `.rabbit-scope-override-used`, `.rabbit-skills-updated`) MUST still be
    consumed exactly once per aggregation pass, even when a higher-priority
    condition is also present in the same emission — suppressing the consume
    would leak the marker to a later invocation and re-fire the alert.
    Conditions at the same priority level do not coexist in the current
    implementation; each has a distinct marker or detection path.

38. The JSON object emitted by `sync-check.py` conforms to the output schema
    above. Shape: `{"systemMessage": "<aggregated string>"}` when no
    CLAUDE.md drift/first-run condition is pending; or
    `{"additionalContext": "<string>", "systemMessage": "<aggregated string>"}`
    when CLAUDE.md drift or first-run is among the pending conditions. The
    `systemMessage` MAY contain multiple `[rabbit] ━━━ ... ━━━` lines — one
    per pending condition, joined by `\n`, in the Inv 37 priority order.
    No other top-level keys are emitted. When NO condition is pending,
    `sync-check.py` emits no JSON at all (exit 0, empty stdout). This
    schema is machine-first: downstream consumers (Claude Code Stop hook
    handler) read `systemMessage` and optionally `additionalContext`; they
    never parse free-form text.

75. `session-init.py` emits AT MOST ONE JSON object per invocation
    (RABBIT-CAGE-BACKLOG-18). When both the R1 branch enforcement and the
    policy injection conditions apply, their rendered `[rabbit] ━━━ ... ━━━`
    lines MUST be combined into a single `systemMessage` (newline-joined; R1
    line first, policy line second), emitted within one JSON object that
    also carries `additionalContext` when policy injection applies. Emitting
    two separate JSON objects per invocation (the pre-BACKLOG-18 behaviour)
    violates the single-emission contract. When neither condition applies,
    `session-init.py` emits no JSON (exit 0, empty stdout). When only one
    condition applies, the emitted JSON contains only that condition's
    line in `systemMessage`.

76. Each `[rabbit]` message-producing condition inside the multi-condition
    hooks (`sync-check.py`, `session-init.py`) is implemented as a
    pure-function renderer (RABBIT-CAGE-BACKLOG-18). A renderer takes the
    state it needs (repo root, marker contents, etc.) and returns either
    `None` (condition does not apply) or a `dict` payload with the keys
    `systemMessage: <str>` and optionally `additionalContext: <str>`.
    Renderers MUST NOT write to stdout, stderr, or any file as a side
    effect of rendering. The hook's `main()` invokes each renderer in
    priority order, collects the non-`None` payloads, and emits a single
    aggregated JSON object via one final `sys.stdout.write` call. Marker
    consumption (deleting `.rabbit-scope-override-used` /
    `.rabbit-skills-updated`) is the renderer's responsibility — done as
    part of the same call that decides the condition applies — so each
    marker is consumed exactly once per aggregation pass regardless of
    which other conditions co-emit. Direct emission from inside a
    condition handler (the pre-BACKLOG-18 pattern of `emit({...}); return 0`
    after the first matching condition) is forbidden in the
    multi-condition hooks. `refresh.py` is a single-condition hook and is
    not required to adopt the renderer pattern, though it MAY for
    consistency.

77. All rabbit-cage hook scripts (`sync-check.py`, `session-init.py`,
    `refresh.py`) MUST import the shared renderer module via:
        sys.path.insert(0, str(repo_root / ".claude/features/contract/scripts"))
        from rabbit_print import rabbit_print, rabbit_subline
    Every `[🐇 rabbit 🐇]` line in the JSON `systemMessage` MUST be the
    return value of one `rabbit_print(message_id, **kwargs)` call (banner)
    or one `rabbit_subline(text, color)` call (sub-line). Inline ANSI
    escape codes (`\x1b[3...`), the literal brand prefix string
    (`[rabbit]` or `[🐇 rabbit 🐇]`), and the bar character (`━━━`) MUST
    NOT appear anywhere in these three hook source files outside of import
    statements or comments referring to the contract. This is the
    consumer-side enforcement of contract Inv 36.

78. The message-id mapping per producer (BACKLOG-19):
    - `session-init.py`: `r1-branch` (with kwarg `branch`), `welcome`
      (no kwargs; sub-lines list the @-import basenames + one-liner
      description via `rabbit_subline`).
    - `refresh.py`: `policy-refreshed` (no kwargs; sub-lines list each
      @-import full path via `rabbit_subline`).
    - `sync-check.py`: `policy-drift`, `surface-drift`,
      `scope-guard-off`, `scope-guard-bypassed`, `human-approval-bypass`,
      `skills-updated` (the last one takes kwarg `names`).
    The welcome banner sub-line text is fixed to:
      `philosophy.md    — machine-first · bounded scope · designed deprecation`
      `spec-rules.md    — determinism first; schema contracts; lifecycle ownership`
      `coding-rules.md  — think first; simplicity; surgical edits; goal-driven TDD`
    Other @-imports (if added later) appear as the basename only with no
    description suffix.

79. `sync-check.py` first-run path (CLAUDE.md not on disk) is REMOVED
    (BACKLOG-19). In any real checkout, CLAUDE.md is committed and exists
    on disk; the path was dead code. The drift path (CLAUDE.md exists but
    diverges from the regenerated content) remains and covers regeneration.
    If CLAUDE.md is genuinely missing, the hook silently exits 0 — bootstrap
    is `install.py`'s responsibility, not `sync-check.py`'s.
