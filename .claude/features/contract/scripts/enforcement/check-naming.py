#!/usr/bin/env python3
# check-naming.py — enforce: every slash command, skill, and subagent under
# <root>/.claude/ MUST have a name beginning with 'rabbit-'.
#
# What is checked:
#   <root>/.claude/commands/*.md  (slash commands; basename without .md)
#   <root>/.claude/agents/*.md    (subagents;     basename without .md)
#   <root>/.claude/skills/*/      (skills;        directory name)
#
# Ignored (not artifact names):
#   README.md, CHANGELOG.md, *.txt, *.json
#
# Usage:  check-naming.py [root]
#         (default root: current working directory)
#
# Exit:
#   0 all artifacts conformant (or no .claude tree)
#   1 one or more violations (each named on stderr)
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when naming enforcement is provided by a native linter.

import os
import sys


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."

    if not os.path.isdir(root):
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        sys.exit(2)

    claude_dir = os.path.join(root, ".claude")
    if not os.path.isdir(claude_dir):
        print(f"OK: no .claude tree at {root} (vacuous)")
        sys.exit(0)

    violations = 0
    flagged_paths = set()

    def flag(label, name, path, reason):
        nonlocal violations
        if path in flagged_paths:
            return
        flagged_paths.add(path)
        print(f"VIOLATION: {label} {path} — {reason} ('{name}')", file=sys.stderr)
        violations += 1

    # Slash commands: .claude/commands/*.md
    commands_dir = os.path.join(claude_dir, "commands")
    if os.path.isdir(commands_dir):
        for fname in os.listdir(commands_dir):
            if not fname.endswith(".md"):
                continue
            base = fname[:-3]
            if base in ("README", "CHANGELOG"):
                continue
            if not base.startswith("rabbit-"):
                path = os.path.join(commands_dir, fname)
                flag("command", base, path, "must start with 'rabbit-'")

    # Subagents: .claude/agents/*.md
    agents_dir = os.path.join(claude_dir, "agents")
    if os.path.isdir(agents_dir):
        for fname in os.listdir(agents_dir):
            if not fname.endswith(".md"):
                continue
            base = fname[:-3]
            if base in ("README", "CHANGELOG"):
                continue
            if not base.startswith("rabbit-"):
                path = os.path.join(agents_dir, fname)
                flag("agent", base, path, "must start with 'rabbit-'")

    # Skills: .claude/skills/*/
    skills_dir = os.path.join(claude_dir, "skills")
    if os.path.isdir(skills_dir):
        for entry in os.listdir(skills_dir):
            full = os.path.join(skills_dir, entry)
            if not os.path.isdir(full):
                continue
            if not entry.startswith("rabbit-"):
                flag("skill", entry, full + "/", "must start with 'rabbit-'")

    # Check for legacy 'rwf-' prefix anywhere under .claude/ except docs/
    docs_path = os.path.join(claude_dir, "docs")
    for dirpath, dirnames, filenames in os.walk(claude_dir):
        # Skip docs/ subtree
        if os.path.abspath(dirpath).startswith(os.path.abspath(docs_path)):
            dirnames.clear()
            continue
        for fname in filenames:
            if fname.startswith("rwf-"):
                fpath = os.path.join(dirpath, fname)
                flag("file", fname, fpath, "legacy 'rwf-' prefix banned (use 'rabbit-' or no prefix)")

    if violations > 0:
        print(f"FAIL: {violations} naming violation(s) under {claude_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: all artifacts under {claude_dir} start with 'rabbit-'; no 'rwf-' prefixes outside docs/")
    sys.exit(0)


if __name__ == "__main__":
    main()
