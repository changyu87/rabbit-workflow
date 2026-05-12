---
feature: rabbit-cage
version: 2.1.0
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
- `CLAUDE.md` — generated file (by `generate-claude-md.sh`); committed to the repo (not gitignored); not a symlink; validated on every Stop against a fresh regeneration from policy sources
- `README.md` — symlink to `rabbit-cage/README.md`
- `install.sh` — symlink to `rabbit-cage/install.sh`

## Invariants

1. `.claude/commands` is a symlink pointing to `.claude/features/rabbit-cage/commands`.
2. `.claude/hooks` is a symlink pointing to `.claude/features/rabbit-cage/hooks`.
3. `.claude/skills` is a real directory (not a symlink) populated by `generate-skills-dir.sh` via recursive copy (`cp -rp`) of each feature's skill source directory; the directory and its contents are committed to the repo (not gitignored).
4. `.claude/settings.json` is a symlink pointing to `.claude/features/rabbit-cage/settings.json`.
5. `.claude/policy` is a symlink pointing to `.claude/features/policy`.
6. `.claude/contract` is a symlink pointing to `.claude/features/contract`.
7. `CLAUDE.md` at repo root is a generated regular file (not a symlink); produced by `generate-claude-md.sh`; committed to the repo (not gitignored); contains inline `rabbit-policy-start`/`rabbit-policy-end` section.
8. `README.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/README.md`.
9. `install.sh` at repo root is a symlink pointing to `.claude/features/rabbit-cage/install.sh`.
10. `CLAUDE.md` contains `@`-imports sourcing files from `.claude/policy/`.

## /rabbit-config Command

`/rabbit-config` is the extensible configuration command for the rabbit workflow. It uses a subcommand pattern to group configuration operations under one entry point.

**Syntax:** `/rabbit-config <subcommand> [value]`

### Subcommand: prompt-threshold

Sets or restores the auto-refresh threshold (number of prompts between policy re-injections).

- `/rabbit-config prompt-threshold <N>` — writes `RBT_REFRESH_EVERY=N` to `.claude/settings.local.json`. `N` must be a positive integer. Takes effect on the next session start.
- `/rabbit-config prompt-threshold` (no value) — removes the `RBT_REFRESH_EVERY` key from `.claude/settings.local.json`, restoring the default value defined in `.claude/settings.json`.

**Error handling:** unknown subcommands produce a usage message listing available subcommands. An invalid value (non-positive-integer) for `prompt-threshold` produces an error and exits without modifying any file.

**Replaces:** `/rabbit-set-threshold` — that command is removed; `prompt-threshold` is its direct functional replacement. The subcommand pattern makes it straightforward to add future configuration subcommands (e.g., `/rabbit-config set-something-else [value]`).

### Invariants

25. `/rabbit-config` command file exists at `commands/rabbit-config.md`.
26. `/rabbit-set-threshold` command file does NOT exist anywhere in the repository.
27. `/rabbit-config prompt-threshold <N>` writes `{"env": {"RBT_REFRESH_EVERY": "<N>"}}` merged into `.claude/settings.local.json`.
28. `/rabbit-config prompt-threshold` (no argument) removes the `RBT_REFRESH_EVERY` key from the `env` object in `.claude/settings.local.json`; if `env` becomes empty the key is also removed.
29. An unknown subcommand to `/rabbit-config` emits a usage message and exits non-zero without modifying any file.

## Out of Scope

- Content authored by other features — rabbit-cage wires their surface, not their content.
- `settings.local.json` — user-local overrides; never written by rabbit-cage except via the `/rabbit-config` command on explicit user request.
- Scripts: rabbit-cage owns no runtime scripts beyond `install.sh` and those registered in its contract.
- Workspace hierarchy display — owned and wired by the `rabbit-workspace-map` skill in the contract feature; rabbit-cage no longer declares it in its `feature.json` skills list.

## Scope-Guard Override

A human-approved override mechanism allows the scope-guard to permit a write
that would otherwise be denied. The override is granted by the human creating
a marker file at the repo root; the act of running the command IS the
approval.

**Marker files (both gitignored, repo-root):**

- `.rabbit-scope-override` — contents are exactly `one-time` or `session`.
  Created by the human (e.g. `echo one-time > .rabbit-scope-override`).
- `.rabbit-scope-override-used` — created by `scope-guard.sh` when a
  `one-time` override is consumed. Acts as a single-shot post-event signal
  for `sync-check.sh` to surface the consumption.

**`scope-guard.sh` semantics** (evaluated before the default-deny step):

- `.rabbit-scope-override` = `session` → ALLOW; marker is left in place so
  the guard remains down for the rest of the session.
- `.rabbit-scope-override` = `one-time` → ALLOW; `scope-guard.sh` DELETES
  `.rabbit-scope-override` and CREATES `.rabbit-scope-override-used`.
- Absent or other content → fall through to the default-deny path.

**`sync-check.sh` semantics** (Stop hook, after the normal drift check):

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
`scope-guard.sh` never creates `.rabbit-scope-override`; it only reads
and (for `one-time`) deletes it.

**Filename allowlist:** `scope-guard.sh` maintains a filename allowlist that
always permits writes regardless of scope-marker state. The allowlisted
basenames are: `settings.json`, `settings.local.json`, `.gitignore`, and
`.rabbit-scope-override`. The `.rabbit-scope-override` entry is required so
that the confirm-token approval flow is not a catch-22: Claude must be able to
write the override file after receiving user approval, even when no scope
marker is active.

## Invariants (additional)

11. `.rabbit-scope-override` and `.rabbit-scope-override-used` are gitignored.
20. `scope-guard.sh` filename allowlist contains exactly: `settings.json`,
    `settings.local.json`, `.gitignore`, and `.rabbit-scope-override`. Writes
    to any of these basenames are always permitted, regardless of scope-marker
    state. This allowlist must include `.rabbit-scope-override` to enable the
    confirm-token approval flow (Claude writes the override file after
    in-conversation user approval without a scope marker active).
12. `scope-guard.sh` never creates `.rabbit-scope-override`; it only reads it
    and (for `one-time`) deletes it after consumption. The main session (Claude)
    may write `.rabbit-scope-override` after receiving explicit in-conversation
    user approval via the confirm-token flow.
13. A `one-time` override consumed by `scope-guard.sh` is acknowledged exactly
    once by `sync-check.sh`, after which `.rabbit-scope-override-used` is
    removed.
14. `generate-skills-dir.sh --check` detects drift by comparing the sha256 of
    each source `SKILL.md` directly against the sha256 of the corresponding
    copy at `.claude/skills/<name>/SKILL.md`. No external baseline file
    (`.rbt-skills-hash`) is used or maintained.
15. `.claude/skills/` and its contents are committed to the repo; neither
    `.claude/skills/` nor `.rbt-skills-hash` appears in `.gitignore`.
16. `CLAUDE.md` at the repo root is committed to the repo; `CLAUDE.md` does
    not appear in `.gitignore`.
17. On every Stop event, `sync-check.sh` compares the committed
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

`session-init.sh` enforces R1 (branch-per-feature; never commit directly to main) at
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

21. On `SessionStart`, `session-init.sh` checks `git branch --show-current`. If the
    result is `main` or `master`, it runs `git checkout -b session/$(date +%Y%m%d-%H%M%S)`
    and emits a green `[rabbit]` systemMessage naming the new branch.
22. If the current branch is not `main` or `master`, `session-init.sh` does NOT create
    or switch to any branch — the branch-enforcement block is a no-op.
23. The created branch name always begins with the prefix `session/` followed by exactly
    eight digits, a hyphen, and six digits (`session/YYYYMMDD-HHMMSS`).
24. `sync-check.sh` detects untracked skill directories under
    `.claude/skills/` or `.claude/features/*/skills/` by invoking
    `git ls-files --others --exclude-standard` against those paths. If any
    untracked path beneath a `skills/` segment is reported, the hook treats
    this as skills drift and emits the green `[rabbit] Skills updated`
    `systemMessage` alert (the same alert emitted when
    `generate-skills-dir.sh --check` reports content drift). This prevents
    new skill directories from sitting untracked indefinitely without user
    notification.

## Scope-Guard Quote Awareness

`extract_bash_targets()` in `scope-guard.sh` is quote-aware. Before applying
any redirect or write-command pattern matching, it strips single-quoted and
double-quoted regions from each command segment using python3. This prevents
false positives when string data (e.g., inside `python3 -c '...'` arguments
or heredoc bodies) contains `>`, `>>`, or command names such as `tee`, `cp`,
`mv`, or `rm`. Real unquoted redirects are still detected correctly.

## Visual Styling

Every `systemMessage` emitted by rabbit-cage hooks (`sync-check.sh`,
`session-init.sh`, `refresh.sh`) is wrapped in ANSI color codes
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
