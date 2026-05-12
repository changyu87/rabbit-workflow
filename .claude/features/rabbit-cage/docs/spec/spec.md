---
feature: rabbit-cage
version: 1.5.0
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
- `CLAUDE.md` — generated file (by `generate-claude-md.sh`); gitignored; not a symlink
- `README.md` — symlink to `rabbit-cage/README.md`
- `install.sh` — symlink to `rabbit-cage/install.sh`

## Invariants

1. `.claude/commands` is a symlink pointing to `.claude/features/rabbit-cage/commands`.
2. `.claude/hooks` is a symlink pointing to `.claude/features/rabbit-cage/hooks`.
3. `.claude/skills` is a real directory (not a symlink) populated by `generate-skills-dir.sh` via recursive copy (`cp -rp`) of each feature's skill source directory; the directory and its contents are committed to the repo (not gitignored).
4. `.claude/settings.json` is a symlink pointing to `.claude/features/rabbit-cage/settings.json`.
5. `.claude/policy` is a symlink pointing to `.claude/features/policy`.
6. `.claude/contract` is a symlink pointing to `.claude/features/contract`.
7. `CLAUDE.md` at repo root is a generated regular file (not a symlink); produced by `generate-claude-md.sh`; gitignored; contains inline `rabbit-policy-start`/`rabbit-policy-end` section.
8. `README.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/README.md`.
9. `install.sh` at repo root is a symlink pointing to `.claude/features/rabbit-cage/install.sh`.
10. `CLAUDE.md` contains `@`-imports sourcing files from `.claude/policy/`.

## Out of Scope

- Content authored by other features — rabbit-cage wires their surface, not their content.
- `settings.local.json` — user-local overrides; never written by rabbit-cage.
- Scripts: rabbit-cage owns no runtime scripts beyond `install.sh` and those registered in its contract.
- Authoring `.rabbit-scope-override` — only a human creates this file. rabbit-cage hooks read and consume it but never create it.

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
  for `rbt-sync-check.sh` to surface the consumption.

**`scope-guard.sh` semantics** (evaluated before the default-deny step):

- `.rabbit-scope-override` = `session` → ALLOW; marker is left in place so
  the guard remains down for the rest of the session.
- `.rabbit-scope-override` = `one-time` → ALLOW; `scope-guard.sh` DELETES
  `.rabbit-scope-override` and CREATES `.rabbit-scope-override-used`.
- Absent or other content → fall through to the default-deny path.

**`rbt-sync-check.sh` semantics** (Stop hook, after the normal drift check):

- `.rabbit-scope-override` = `session` → emit a red `[rabbit]` systemMessage
  on every Stop, signalling that the guard is currently off.
- `.rabbit-scope-override-used` exists → emit the same red alert once, then
  DELETE `.rabbit-scope-override-used`.

**Human approval flow:** when scope-guard blocks a write, Claude instructs
the user to run `echo one-time > .rabbit-scope-override` or
`echo session > .rabbit-scope-override`. Claude itself never writes either
marker.

## Invariants (additional)

11. `.rabbit-scope-override` and `.rabbit-scope-override-used` are gitignored.
12. `scope-guard.sh` never creates `.rabbit-scope-override`; it only reads it
    and (for `one-time`) deletes it after consumption.
13. A `one-time` override consumed by `scope-guard.sh` is acknowledged exactly
    once by `rbt-sync-check.sh`, after which `.rabbit-scope-override-used` is
    removed.
14. `generate-skills-dir.sh --check` detects drift by comparing the sha256 of
    each source `SKILL.md` directly against the sha256 of the corresponding
    copy at `.claude/skills/<name>/SKILL.md`. No external baseline file
    (`.rbt-skills-hash`) is used or maintained.
15. `.claude/skills/` and its contents are committed to the repo; neither
    `.claude/skills/` nor `.rbt-skills-hash` appears in `.gitignore`.

## Scope-Guard Quote Awareness

`extract_bash_targets()` in `scope-guard.sh` is quote-aware. Before applying
any redirect or write-command pattern matching, it strips single-quoted and
double-quoted regions from each command segment using python3. This prevents
false positives when string data (e.g., inside `python3 -c '...'` arguments
or heredoc bodies) contains `>`, `>>`, or command names such as `tee`, `cp`,
`mv`, or `rm`. Real unquoted redirects are still detected correctly.

## Visual Styling

Every `systemMessage` emitted by rabbit-cage hooks (`rbt-sync-check.sh`,
`rbt-session-init.sh`, `rbt-refresh.sh`) is wrapped in ANSI deep-green color
codes (`\x1b[32m` … `\x1b[0m`). Markdown is not rendered in `systemMessage`
output; ANSI escape codes are. The deep-green color marks all `[rabbit]`
status/drift/refresh messages as system-emitted (not user-emitted), making
them visually distinguishable in the Claude Code transcript.

Scope-guard override alerts emitted by `rbt-sync-check.sh` use ANSI red
(`\x1b[31m` … `\x1b[0m`) instead of deep-green, marking them as elevated
warnings:

    \x1b[31m🔓 ━━━ [rabbit] SCOPE GUARD OFF (session override active) ━━━ 🔓\x1b[0m
