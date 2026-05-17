---
feature: rabbit-cage
version: 2.6.0
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

- **allow**: `Bash(*)` — every bash command runs without prompting.
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

### Invariants

51. `.claude/features/rabbit-cage/settings.json` declares a top-level `permissions`
    object whose `allow` array contains exactly the entry `Bash(*)` and whose `deny`
    array contains exactly the entries `Bash(git merge *)`, `Bash(git push * main)`,
    and `Bash(git push origin main)`. The build-managed copy at `.claude/settings.json`
    holds the same `permissions` block by virtue of being a `copy-file` target of the
    source. No other top-level keys (`env`, `hooks`) are altered by this invariant.

## /rabbit-config Command

`/rabbit-config` is the extensible configuration command for the rabbit workflow. It uses a subcommand pattern to group configuration operations under one entry point.

**Syntax:** `/rabbit-config <subcommand> [value]`

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

**Common rules for permission subcommands (`allowed-tools`, `bash-allow`):**

- The target file is `.claude/settings.local.json` (not `.claude/settings.json`). `settings.local.json` is outside the build system's copy-file target set, so permissions persist across `sync-check.py` surface-drift rebuilds. Writes to `settings.local.json` are unconditionally permitted by the scope-guard filename allowlist.
- If `permissions` or `permissions.allow` is missing from `settings.local.json`, `add` creates it as needed. `remove` on a missing key is a no-op (exit 0).
- After removal, if `permissions.allow` becomes empty, the key remains as an empty array (it is not deleted); if `permissions` itself becomes the only key and is `{"allow": []}`, it is left in place. The shape of `settings.local.json` other than the `permissions.allow` array is never modified by these subcommands.
- Output of `add` and `remove` is a single confirmation line on stdout (e.g. `Added Bash(touch:*) to .claude/settings.local.json`); no output if the operation was a no-op other than `Already present` / `Not present`.
- List operations (no-action form of `allowed-tools` and `bash-allow`) read from `.claude/settings.local.json` only. The canonical surface source `.claude/features/rabbit-cage/settings.json` MAY declare a `permissions` block holding team-wide defaults (see "Team-wide Permissions" below); `.claude/settings.json` is its build-managed copy. Claude Code merges permission arrays across all settings sources (user → project → local), so team-wide defaults from `settings.json` and personal entries from `settings.local.json` compose. Neither `settings.json` nor its source is consulted by list operations — list operations remain scoped to personal `settings.local.json` entries.

**Error handling:** unknown subcommands produce a usage message listing available subcommands. An invalid value (non-positive-integer) for `prompt-threshold`, an empty `<tool>`/`<command>`, an invalid `<command>` for `bash-allow` (containing `(`, `)`, `:`, or whitespace), an unknown action for `allowed-tools` or `bash-allow` (anything other than `add`, `remove`, or no action), or a `Bash(...)`-shaped value passed to `allowed-tools add`/`remove` all produce an error and exit non-zero without modifying any file.

**Replaces:** `/rabbit-set-threshold` — that command is removed; `prompt-threshold` is its direct functional replacement. The subcommand pattern makes it straightforward to add future configuration subcommands (e.g., `/rabbit-config set-something-else [value]`).

### Invariants

25. `/rabbit-config` command file exists at `commands/rabbit-config.md`.
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
basenames are: `settings.json`, `settings.local.json`, `.gitignore`, and
`.rabbit-scope-override`. The `.rabbit-scope-override` entry is required so
that the confirm-token approval flow is not a catch-22: Claude must be able to
write the override file after receiving user approval, even when no scope
marker is active.

## Invariants (additional)

11. `.rabbit-scope-override` and `.rabbit-scope-override-used` are gitignored.
20. `scope-guard.py` filename allowlist contains exactly: `settings.json`,
    `settings.local.json`, `.gitignore`, and `.rabbit-scope-override`. Writes
    to any of these basenames are always permitted, regardless of scope-marker
    state. This allowlist must include `.rabbit-scope-override` to enable the
    confirm-token approval flow (Claude writes the override file after
    in-conversation user approval without a scope marker active).
12. `scope-guard.py` never creates `.rabbit-scope-override`; it only reads it
    and (for `one-time`) deletes it after consumption. The main session (Claude)
    may write `.rabbit-scope-override` after receiving explicit in-conversation
    user approval via the confirm-token flow.
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
18. `[rabbit]` `systemMessage` color convention: normal/info messages use
    ANSI green (`\x1b[32m`); alert/error messages use ANSI red
    (`\x1b[31m`). Specifically: drift detection (CLAUDE.md drift, skills
    drift, policy drift) and scope-guard-off messages are red;
    session-init, refresh, and skills-updated messages are green.
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
    This check runs only when all previous checks (CLAUDE.md drift, surface
    drift, override alerts) did NOT emit JSON. The single-JSON-per-invocation
    invariant is preserved: at most one JSON object is emitted per
    sync-check.py invocation.
    (f) The multi-message output strategy is **conditional-priority**: only the
    highest-priority pending condition emits per Stop invocation. Lower-priority
    conditions are suppressed until the higher-priority condition clears.
    This strategy is chosen because the Claude Code Stop hook protocol accepts
    at most one JSON object per invocation; emitting multiple would violate the
    hook contract. The priority order is declared explicitly in Invariant 37.

## Scope-Guard Quote Awareness

`extract_bash_targets()` in `scope-guard.py` is quote-aware. Before applying
any redirect or write-command pattern matching, it strips single-quoted and
double-quoted regions from each command segment using Python's `re` module.
This prevents false positives when string data (e.g., inside `python3 -c '...'`
arguments or heredoc bodies) contains `>`, `>>`, or command names such as
`tee`, `cp`, `mv`, or `rm`. Real unquoted redirects are still detected correctly.

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
32. `sync-check.py` reads and writes `.rabbit-sync-counter`; reads `RABBIT_SYNC_EVERY`; writes `.rabbit-prompt-counter` on first-run and drift paths; reads `RABBIT_REFRESH_EVERY` for that counter write.
33. `settings.json` declares env key `RABBIT_REFRESH_EVERY`; its `SessionStart` command resets `.rabbit-prompt-counter`.
34. `rabbit-refresh.md` command resets `.rabbit-prompt-counter`.
35. `workspace-tree.py` excludes `.rabbit-prompt-counter` from full listings.

## sync-check.py Output Schema

`sync-check.py` emits at most one JSON object per invocation to stdout. The output schema is:

```json
{
  "additionalContext": "<string — optional; only present on first-run or drift-detected paths>",
  "systemMessage": "<string — ANSI-colored [rabbit] message>"
}
```

`systemMessage` is always present when JSON is emitted. `additionalContext` is present only on CLAUDE.md-related paths (first-run and drift-detected). All other conditions emit `systemMessage` only.

### Invariants

37. `sync-check.py` uses the **conditional-priority** multi-message strategy: exactly one
    condition emits per Stop invocation; lower-priority conditions are suppressed until
    the higher-priority condition clears. The explicit priority order (highest to lowest):
    1. CLAUDE.md drift or first-run (always exits immediately after emitting)
    2. Surface drift (copy-file targets out of sync with sources)
    3. Scope-guard-off (session override active or one-time override consumed)
    4. Skills-updated (`.rabbit-skills-updated` marker present)
    Conditions at the same priority level do not coexist in the current implementation;
    each has a distinct marker or detection path.

38. Every JSON object emitted by `sync-check.py` conforms to the output schema above:
    `{"systemMessage": "<ANSI-colored string>"}` for conditions 2–4; 
    `{"additionalContext": "<string>", "systemMessage": "<ANSI-colored string>"}` for
    condition 1 (CLAUDE.md drift/first-run). No other top-level keys are emitted.
    This schema is machine-first: downstream consumers (Claude Code Stop hook handler)
    read `systemMessage` and optionally `additionalContext`; they never parse free-form text.
