---
feature: rabbit-cage
version: 2.4.0
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
3. `.claude/skills` is a real directory (not a symlink) populated by `build.sh` (via `build-contract.json` copy-file targets) from each feature's skill source directory; the directory and its contents are committed to the repo (not gitignored).
4. `.claude/settings.json` is a symlink pointing to `.claude/features/rabbit-cage/settings.json`.
5. `.claude/policy` is a symlink pointing to `.claude/features/policy`.
6. `.claude/contract` is a symlink pointing to `.claude/features/contract`.
7. `CLAUDE.md` at repo root is a generated regular file (not a symlink); produced by `generate-claude-md.sh`; committed to the repo (not gitignored); contains inline `rabbit-policy-start`/`rabbit-policy-end` section.
8. `README.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/README.md`.
9. `install.sh` at repo root is a symlink pointing to `.claude/features/rabbit-cage/install.sh`.
10. `CLAUDE.md` contains `@`-imports sourcing files from `.claude/policy/`.
25. `.claude/features/rabbit-cage/scripts/build.sh` exists and is executable; reads `build-contract.json` and builds all declared targets.
26. `.claude/features/rabbit-cage/test/test-generated-surface.sh` exists and exits 0 on a clean workspace (all check_on_stop copy-file targets match their sources).
27. `generate-skills-dir.sh` does NOT exist in `.claude/features/rabbit-cage/scripts/` (deleted; superseded by build.sh + build-contract.json).
28. `test-symlinks.sh` does NOT exist in `.claude/features/rabbit-cage/test/` (deleted; superseded by test-generated-surface.sh).
29. `surface.hooks`, `surface.commands`, and `surface.settings` in `feature.json` are all `[]` (empty arrays); hooks, commands, and settings are now managed via build-contract.json copy-file targets.
30. `build.sh` passes `RABBIT_ROOT=<repo_root>` as an environment variable when invoking `generate-claude-md.sh` for `generate-claude-md` targets, so that installs into non-git directories (e.g., temp dirs during `install.sh`) succeed without `git rev-parse` errors.
39. All Python logic extracted from bash scripts lives in standalone `.py` helper files under `.claude/features/rabbit-cage/scripts/`; the `.sh` scripts invoke them as `python3 <helper>.py`. No bash script in rabbit-cage contains embedded python3 heredocs (`python3 - ... <<'PYEOF'`) or inline `python3 -c` calls.
40. The standalone Python helpers are: `workspace-tree.py` (invoked by `workspace-tree.sh`), `rabbit-project-set-path.py`, `rabbit-project-map.py`, `rabbit-project-consolidate.py` (invoked by `rabbit-project.sh`), `build-targets.py` (invoked by `build.sh`), and `generate-claude-md-header.py` (invoked by `generate-claude-md.sh`).

## /rabbit-config Command

`/rabbit-config` is the extensible configuration command for the rabbit workflow. It uses a subcommand pattern to group configuration operations under one entry point.

**Syntax:** `/rabbit-config <subcommand> [value]`

### Subcommand: prompt-threshold

Sets or restores the auto-refresh threshold (number of prompts between policy re-injections).

- `/rabbit-config prompt-threshold <N>` — writes `RABBIT_REFRESH_EVERY=N` to `.claude/settings.local.json`. `N` must be a positive integer. Takes effect on the next session start.
- `/rabbit-config prompt-threshold` (no value) — removes the `RABBIT_REFRESH_EVERY` key from `.claude/settings.local.json`, restoring the default value defined in `.claude/settings.json`.

**Error handling:** unknown subcommands produce a usage message listing available subcommands. An invalid value (non-positive-integer) for `prompt-threshold` produces an error and exits without modifying any file.

**Replaces:** `/rabbit-set-threshold` — that command is removed; `prompt-threshold` is its direct functional replacement. The subcommand pattern makes it straightforward to add future configuration subcommands (e.g., `/rabbit-config set-something-else [value]`).

### Invariants

25. `/rabbit-config` command file exists at `commands/rabbit-config.md`.
26. `/rabbit-set-threshold` command file does NOT exist anywhere in the repository.
27. `/rabbit-config prompt-threshold <N>` writes `{"env": {"RABBIT_REFRESH_EVERY": "<N>"}}` merged into `.claude/settings.local.json`.
28. `/rabbit-config prompt-threshold` (no argument) removes the `RABBIT_REFRESH_EVERY` key from the `env` object in `.claude/settings.local.json`; if `env` becomes empty the key is also removed.
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

**Revoking a session override (scope guard back on):** A session override
stays in place until explicitly revoked. To revoke it, run:

    bash .claude/features/rabbit-cage/scripts/scope-guard-on.sh

`scope-guard-on.sh` deletes `.rabbit-scope-override` (if present) and
emits a confirmation message. After revocation the guard returns to its
default-deny posture immediately — no session restart is required. The
script is a no-op if no override is active.

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
41. `scope-guard-on.sh` exists at `.claude/features/rabbit-cage/scripts/scope-guard-on.sh`
    and is executable. It deletes `.rabbit-scope-override` (if present) and prints a
    confirmation to stdout. It is a no-op if no override file exists. It is the
    canonical answer to "scope guard back on" / "revoke the session override".
42. The double-quoted region stripping `re.sub` in `extract_bash_targets()` of
    `scope-guard.sh` uses the `re.DOTALL` flag so that multi-line double-quoted
    strings (e.g., from backslash-newline continuations) are fully removed before
    pattern matching, preventing false-positive DENY on content inside the string.
14. `generate-skills-dir.sh --check` detects drift by comparing the sha256 of
    each source `SKILL.md` directly against the sha256 of the corresponding
    copy at `.claude/skills/<name>/SKILL.md`. No external baseline file is
    used or maintained.
15. `.claude/skills/` and its contents are committed to the repo;
    `.claude/skills/` does not appear in `.gitignore`.
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
24. On every Stop event, after the existing drift checks, `sync-check.sh`
    detects skill updates via a self-clearing marker file:
    (a) `build-targets.py` (invoked by `build.sh`) appends the skill name to
    `.rabbit-skills-updated` at the repo root whenever it copies a `copy-file`
    target whose destination matches the regex `^\.claude/skills/([^/]+)/SKILL\.md$`.
    Each appended line is the captured skill name followed by a newline. The
    marker is NOT written for non-SKILL.md targets, nor for targets under
    `.claude/commands/` or `.claude/agents/`.
    (b) `sync-check.sh` checks if `.rabbit-skills-updated` exists at the repo root.
    If it does: read the comma-joined list of skill names, delete the marker
    (self-clearing — alert fires exactly once per build), and emit a green
    `[rabbit]` `systemMessage` naming the updated skills. Exact message format:
    `[rabbit] Skills updated: <names> — will reload automatically on next invocation.`
    where `<names>` is the comma-joined skill names from the marker.
    If `.rabbit-skills-updated` is absent: silent (no output).
    No git diff is performed; the marker file IS the signal.
    (c) `session-init.sh` does NOT reference `.rabbit-skills-updated`. Session-
    start clearing is unnecessary because `sync-check.sh` self-clears the marker
    on first read.
    (d) The `/rabbit-refresh` command does NOT reference `.rabbit-skills-updated`
    for the same reason — the marker is consumed by `sync-check.sh`.
    (e) `.rabbit-skills-updated` is gitignored.
    This check runs only when all previous checks (CLAUDE.md drift, surface
    drift, override alerts) did NOT emit JSON. The single-JSON-per-invocation
    invariant is preserved: at most one JSON object is emitted per
    sync-check.sh invocation.
    (f) The multi-message output strategy is **conditional-priority**: only the
    highest-priority pending condition emits per Stop invocation. Lower-priority
    conditions are suppressed until the higher-priority condition clears.
    This strategy is chosen because the Claude Code Stop hook protocol accepts
    at most one JSON object per invocation; emitting multiple would violate the
    hook contract. The priority order is declared explicitly in Invariant 37.

## Scope-Guard Quote Awareness

`extract_bash_targets()` in `scope-guard.sh` is quote-aware. Before applying
any redirect or write-command pattern matching, it strips single-quoted and
double-quoted regions from each command segment using python3. This prevents
false positives when string data (e.g., inside `python3 -c '...'` arguments
or heredoc bodies) contains `>`, `>>`, or command names such as `tee`, `cp`,
`mv`, or `rm`. Real unquoted redirects are still detected correctly.

The double-quoted region stripping `re.sub` call uses the `re.DOTALL` flag
(or equivalently `re.S`) so that quoted regions spanning multiple lines
(e.g., a `--description "..."` argument split across lines with
backslash-newline continuations) are fully removed before pattern matching.
Without `re.DOTALL`, `.` does not match newlines, so multi-line quoted
strings are only partially stripped, causing false-positive DENY on content
inside the string (e.g., `-> U+00F0`).

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

## Runtime Artifact Naming

Runtime counter and config files use the `rabbit-` prefix (not `rbt-`).

- Prompt counter: `.rabbit-prompt-counter` (repo root, gitignored)
- Sync counter: `.rabbit-sync-counter` (repo root, gitignored)
- Prompt threshold env var: `RABBIT_REFRESH_EVERY` (default `20`, in `settings.json` and `settings.local.json`)
- Sync threshold env var: `RABBIT_SYNC_EVERY` (default `1`)

### Invariants

31. `refresh.sh` reads and writes `.rabbit-prompt-counter`; reads `RABBIT_REFRESH_EVERY`.
32. `sync-check.sh` reads and writes `.rabbit-sync-counter`; reads `RABBIT_SYNC_EVERY`; writes `.rabbit-prompt-counter` on first-run and drift paths; reads `RABBIT_REFRESH_EVERY` for that counter write.
33. `settings.json` declares env key `RABBIT_REFRESH_EVERY`; its `SessionStart` command resets `.rabbit-prompt-counter`.
34. `rabbit-refresh.md` command resets `.rabbit-prompt-counter`.
35. `workspace-tree.sh` excludes `.rabbit-prompt-counter` from full listings.

## sync-check.sh Output Schema

`sync-check.sh` emits at most one JSON object per invocation to stdout. The output schema is:

```json
{
  "additionalContext": "<string — optional; only present on first-run or drift-detected paths>",
  "systemMessage": "<string — ANSI-colored [rabbit] message>"
}
```

`systemMessage` is always present when JSON is emitted. `additionalContext` is present only on CLAUDE.md-related paths (first-run and drift-detected). All other conditions emit `systemMessage` only.

### Invariants

37. `sync-check.sh` uses the **conditional-priority** multi-message strategy: exactly one
    condition emits per Stop invocation; lower-priority conditions are suppressed until
    the higher-priority condition clears. The explicit priority order (highest to lowest):
    1. CLAUDE.md drift or first-run (always exits immediately after emitting)
    2. Surface drift (copy-file targets out of sync with sources)
    3. Scope-guard-off (session override active or one-time override consumed)
    4. Skills-updated (`.rabbit-skills-updated` marker present)
    Conditions at the same priority level do not coexist in the current implementation;
    each has a distinct marker or detection path.

38. Every JSON object emitted by `sync-check.sh` conforms to the output schema above:
    `{"systemMessage": "<ANSI-colored string>"}` for conditions 2–4; 
    `{"additionalContext": "<string>", "systemMessage": "<ANSI-colored string>"}` for
    condition 1 (CLAUDE.md drift/first-run). No other top-level keys are emitted.
    This schema is machine-first: downstream consumers (Claude Code Stop hook handler)
    read `systemMessage` and optionally `additionalContext`; they never parse free-form text.
