---
name: rabbit-spec-create
description: Draft the initial body of docs/spec/spec.md for a newly-declared rabbit feature by dispatching the read-only spec-creator subagent. Use when a fresh feature has been scaffolded and needs its first spec draft — phrases like "draft a spec for X", "seed the spec for X", "create initial spec for X", "/rabbit-spec-create". Works in both modes: standalone (no globs — produces a skeleton from feature name alone) and plugin (with globs — drafts from real user code). Single-feature per invocation. Invoke as Skill("rabbit-spec-create", args: "<feature-name>") for a skeleton, or Skill("rabbit-spec-create", args: "<feature-name> <glob1> <glob2> ...") to read from code.
version: 1.0.0
owner: rabbit-workflow team
deprecation_criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
---

# rabbit-spec-create — Initial Spec Drafting Skill

Your job: drive the spec-creator subagent to produce a draft `docs/spec/spec.md` body for a newly-declared feature, then write that body to disk under the correct path for the current rabbit mode.

This is a thin orchestration wrapper. The reading-and-drafting work happens in the subagent (read-only, parallel-safe); your role is to assemble the prompt, dispatch the agent, and persist the result.

## Inputs

Args format: `<feature-name> [<glob1> <glob2> ...]`

- **feature-name**: lowercase kebab-case identifier of the target feature (e.g. `my-tool`). The feature directory MUST already exist (scaffolded by `rabbit-feature-new` or its successor). This skill does NOT create the directory.
- **globs** (optional): shell-style path globs the spec-creator will read from. Standalone mode (no globs) produces a skeleton from the feature name alone; plugin mode (one or more globs) drafts from the matched code.

## Modes

Mode is auto-detected from `<repo>/.rabbit/.runtime/mode` (written at SessionStart by `rabbit-meta`'s `write_mode_marker`).

| Mode | Spec path the draft is written to |
|---|---|
| Standalone (marker absent or `standalone`) | `.claude/features/<feature-name>/docs/spec/spec.md` |
| Plugin (marker contains `plugin`) | `<repo>/.rabbit/rabbit-project/features/<feature-name>/docs/spec/spec.md` |

The mode affects only the destination path — the agent's drafting behavior is the same in both modes (it adapts to whether the resolved file list is empty or not).

## Protocol

### Step 1 — Assemble the prompt

Shell out to the dispatcher script. It resolves globs against the repo root, caps the resolved file list at 50 entries, and invokes the shared prompt assembler:

```bash
python3 .claude/features/rabbit-spec/scripts/dispatch-spec-create.py \
  --feature-name <feature-name> \
  --paths "<glob1>,<glob2>,..."
```

In standalone mode (no globs), pass `--paths ""` (an empty string is accepted and produces a skeleton).

The script prints the absolute path of the assembled prompt file to stdout on success. Exit codes: 0 success, 1 invocation error, 2 prompt-assembler failure. Surface non-zero exits to the caller and stop.

### Step 2 — Dispatch the spec-creator subagent

Read the assembled prompt file, then invoke the agent. This is a Claude tool call, not a shell command:

```text
Agent(subagent_type: "spec-creator", prompt: <file contents>)
```

The subagent is tool-restricted to Read/Grep/Glob — it cannot write, edit, or shell out. It returns a six-section spec body as its final message:

1. `## Purpose`
2. `## Paths governed`
3. `## Public surface`
4. `## Current behaviour`
5. `## Known gaps`
6. `## Open questions`

In standalone mode (empty file list) the agent emits a skeleton with `(TBD)` placeholders; in plugin mode it drafts from observed code. Either output is the *initial* draft — the user reviews and edits before the spec is final.

### Step 3 — Write the draft to spec.md

Resolve the destination path from the detected mode, then write the agent's returned body. Preserve any existing YAML frontmatter at the top of the file (the scaffold step writes the frontmatter; this skill only writes the body that follows it).

If `docs/spec/spec.md` does not exist at the destination, write a new file beginning with a minimal frontmatter block (`feature`, `version: 1.0.0`, `owner`, `template_version: 2.0.0`, `status: active`) followed by the draft body.

### Step 4 — Report

Tell the caller the path of the written file and a one-line summary of what the agent observed (e.g. "12 files inspected, 6 entry points named"). The user reviews the draft and edits it before adopting it as the feature's working spec.

## When to use vs not

**Use** when:
- A new feature has just been scaffolded and `docs/spec/spec.md` is empty or contains only template placeholders
- A `rabbit-decompose` workflow has emitted a list of accepted features and each needs a first-pass spec body in parallel
- The user explicitly asks to seed or draft an initial spec for a named feature

**Don't use** when:
- The feature's spec.md already has substantive content — use `rabbit-spec-update` (Stage 3) for revisions, not this skill
- The feature directory hasn't been scaffolded yet — call `rabbit-feature-new` (or its successor) first
- The intent is to revise an existing spec based on new requirements — that's `rabbit-spec-update`'s job

## Why the agent is read-only

The spec-creator agent's tool surface is restricted to Read, Grep, and Glob in its frontmatter — it cannot write, edit, or shell out. This is load-bearing: the agent draws conclusions from observed code, and a write-capable agent could (in principle) modify the code it's drafting against. The read-only constraint makes that impossible regardless of what the agent attempts, so the draft you receive is an honest summary of what's actually on disk.

The skill itself (this file) does the writing, after the user has had a chance to review the agent's output in the conversation.
