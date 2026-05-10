# scope-guard

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](./feature.json).

**Version: 2.0.0**

## Purpose

Repo-wide default-deny write enforcement: every Write/Edit/Bash that
targets any path inside the repo root is denied unless an active scope
marker exists in some ancestor directory, or the filename is on the
allowlist (`settings.json`, `settings.local.json`). Writes outside the
repo root are unrestricted.

This upgrades from v1 (feature-dir-only deny) to v2 (repo-wide deny).
The v1 logic only blocked writes inside feature directories (paths with a
`feature.json` ancestor). The v2 logic applies to the entire repo root,
closing the gap where plain non-feature files could be written without a
scope marker.

## Mechanism

Two pieces:

1. **`.claude/hooks/scope-guard.sh` v2.0.0** — the hook script. Reads the
   `PreToolUse` JSON on stdin. Determines write targets:
   - `Write` / `Edit` → `tool_input.file_path`
   - `Bash` → parses `tool_input.command` for redirections (`>`, `>>`),
     and for write commands (`tee`, `sed -i`, `cp`, `mv`, `rm`, `touch`,
     `mkdir`).
   - For each target, applies the v2 decision logic:
     1. Outside the repo root entirely → allow unconditionally.
     2. Basename is `.rabbit-scope-active` → allow (marker file is exempt).
     3. Basename is `settings.json` or `settings.local.json` → allow (allowlisted).
     4. A `.rabbit-scope-active` marker exists in some ancestor → allow.
     5. Default → deny with a descriptive message.

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

- **Allowlisted filenames.** `settings.json` and `settings.local.json`
  are always allowed regardless of location. These are managed by the
  `update-config` skill and must remain writable without a scope marker.

- **Targets outside the repo root entirely.** Files in `/tmp`, `~`, or
  any path not under the repo root (e.g. `~/.bashrc`) are unrestricted.
  Scope-guard only governs paths inside the repo.

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

`test/run.sh` runs `test-scope-guard.sh` (18 cases):

- g1: Write outside repo root → allow
- g2: Write in feature dir without marker → deny
- g3: Write in feature dir with marker → allow
- g4: Edit out-of-scope → deny
- g5: Bash redirection out-of-scope → deny
- g6: Bash redirection to path outside repo → allow
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
- g17: v2 plain repo-root write without marker → deny
- g18: v2 plain repo-root write with ancestor marker → allow
