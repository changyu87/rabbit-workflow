---
name: rabbit-workspace
description: Use when you need to see the workspace structure, understand how features are organized, or orient yourself in the repo layout. Prints an annotated ASCII hierarchy of the rabbit workflow workspace.
version: 1.0.0
owner: rabbit-cage
deprecation_criterion: when a native Claude Code workspace-view command supersedes this script
---

## Overview

Runs `workspace-tree.sh` to print an annotated ASCII hierarchy of the rabbit workflow workspace, showing structural directories and key files with inline explanations of each node's role.

## Usage

Structural view (dirs + key files only):
```
bash .claude/features/rabbit-cage/scripts/workspace-tree.sh
```

Full view (all files except .swp, .git/*, .rbt-prompt-counter):
```
bash .claude/features/rabbit-cage/scripts/workspace-tree.sh --full
```

## Skill Invocation

When this skill is invoked, run:
```
bash .claude/features/rabbit-cage/scripts/workspace-tree.sh
```
and display the output to the user.

## When to Use

- Before starting work on a feature to understand where files live
- When orienting a new agent or session in the repo
- When the user asks "what's in this repo" or "show me the structure"
- When debugging a missing file or broken symlink by first seeing the layout
