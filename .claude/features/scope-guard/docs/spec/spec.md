# scope-guard

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](./feature.json).

## Purpose

Active enforcement of the unified work model: every Write/Edit/Bash that
targets a path inside a feature directory MUST have an active scope marker
in some ancestor directory. Otherwise it is denied at the harness level
(`exit 2`).

This replaces the earlier `claude-write-lockdown` approach (static
`Write(.claude/**)`/`Edit(.claude/**)` deny rules in shared
`.claude/settings.json`). The static rules were too coarse — they treated
`.claude/` as special, blocked even legitimate dispatcher writes, and
didn't extend to user-mode features in arbitrary paths.

## Mechanism

Two pieces:

1. **`.claude/hooks/scope-guard.sh`** — the hook script. Reads the
   `PreToolUse` JSON on stdin. Determines write targets:
   - `Write` / `Edit` → `tool_input.file_path`
   - `Bash` → parses `tool_input.command` for redirections (`>`, `>>`),
     and for write commands (`tee`, `sed -i`, `cp`, `mv`, `rm`, `touch`,
     `mkdir`).
   - For each target, walks up the path looking for a `.rabbit-scope-active`
     marker. If found anywhere in ancestry, allows. Else: walks up looking
     for a `feature.json` ancestor; if found, denies (target is in a
     feature dir but no active scope); if not found, allows (plain user
     file outside any feature).

2. **`.claude/settings.json` — `PreToolUse` matcher `Write|Edit|Bash`**
   wires the hook. Activated on every session start.

## The protocol

The dispatcher (typically the main session, sometimes another subagent):

```bash
touch "<SCOPE>/.rabbit-scope-active"
# ... Agent dispatch with subagent_type: rabbit-breeder, prompt: "SCOPE: <SCOPE>; ..."
rm "<SCOPE>/.rabbit-scope-active"
```

The breeder (or any agent operating within the scope) writes naturally;
the hook validates each write against the marker. Out-of-scope attempts
are blocked.

## Exemptions

- **The marker file itself.** Writes to (or removals of) any file named
  `.rabbit-scope-active` are exempt — chicken-and-egg. The dispatcher
  must be able to create and remove it.

- **Targets outside any feature directory.** Plain user files (e.g.
  `~/.bashrc`, `/tmp/foo`, `projA/src/app.js`) have no `feature.json`
  ancestor, so the hook allows them unconditionally. Scope-guard only
  cares about feature-directory writes.

## Parallel-dispatch safety

Markers are per-feature-dir, not global. Multiple breeders running
concurrently each touch their own scope's marker; the hook walks each
target's path independently and finds the right marker (or none).

**Residual gap:** the hook can detect "is this target inside *some*
active scope?" but not "is it inside *this specific breeder's* scope" —
Claude Code's hook input doesn't currently expose subagent invocation
identity. So a misbehaving breeder writing into another active breeder's
scope would not be blocked. Convention plus PR review handles that case.
When/if Anthropic exposes subagent identity in hook input, the strict
version becomes a one-line lookup.

## Bash command parsing limits

The hook uses regex-based heuristics for Bash. Reliably catches:

- `> file`, `>> file` (redirections)
- `tee file`, `tee -a file`
- `sed -i ... file`
- `cp src dst`, `mv src dst` (last token is target)
- `rm path[s]`, `touch path[s]`, `mkdir path[s]`

Misses (allowed by default — honest about parsing limits):

- Complex pipelines that compute target paths dynamically
- `dd of=path`, `awk > path` inside subshells, `python -c '...'` writes
- Eval-style obfuscation

For these gaps, the breeder's system prompt and PR review are the
remaining defenses.

## What this feature does NOT define

- The breeder agent itself — that is `breeder` (PR #5).
- The vet agent — that is `vet` (PR #7).
- The schema of feature directories — that is `feature-skeleton`.
- The TDD state machine — that is `tdd-state-machine`.

Bounded scope: this feature owns the **hook + the wiring**. The convention
that the marker should be set/cleared by the dispatcher is documented in
the `breeder` spec.

## Tests

`test/run.sh` runs `test-scope-guard.sh` (16 cases):

- g1: Write outside any feature dir → allow
- g2: Write in feature dir without marker → deny
- g3: Write in feature dir with marker → allow
- g4: Edit out-of-scope → deny
- g5: Bash redirection out-of-scope → deny
- g6: Bash redirection to non-feature path → allow
- g7: Write to marker file is exempt
- g8: Bash rm of marker file is exempt
- g9: Bash read-only command (cat) → allow
- g10: deep nested write under marker-bearing feature dir → allow
- g11: parallel scopes — both writes allowed via independent markers
- g12: Bash touch in scope → allow
- g13: Bash touch out-of-scope → deny
- g14: Bash sed -i out-of-scope → deny
- g15: Bash mv into scope dir without marker → deny
- g16: ungated tool (Read) → allow without check
