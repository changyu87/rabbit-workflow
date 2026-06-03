#!/usr/bin/env python3
"""dispatch-spec-create.py — assemble the rabbit-spec-creator subagent prompt.

Used by the rabbit-spec-create skill (and by rabbit-decompose's downstream
pipeline) when a new feature's initial spec body needs to be drafted.
Resolves the declared path globs, caps the resolved file list at 50 entries,
and invokes contract/scripts/build-prompt.py to assemble the prompt.

Both modes are supported:
  - Plugin mode: --paths populated with code globs the agent reads from.
  - Standalone mode: --paths empty (or omitted) — agent produces a skeleton.

Usage:
    dispatch-spec-create.py --feature-name <name> [--paths <glob1>,<glob2>,...] [--description <text>]

Prints the absolute path of the assembled prompt file to stdout on success.

Exit codes:
    0 = success
    1 = invocation error (missing args, glob resolution failure)
    2 = build-prompt.py subprocess failure

Version: 1.1.1
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
"""

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

MAX_FILES = 50


def main():
    parser = argparse.ArgumentParser(description="Dispatch the rabbit-spec-creator subagent prompt")
    parser.add_argument("--feature-name", required=True, help="Feature name (kebab-case)")
    parser.add_argument("--paths", default="", help="Comma-separated path globs (empty in standalone mode)")
    args = parser.parse_args()

    globs = [g.strip() for g in args.paths.split(",") if g.strip()]

    resolved = []
    for g in globs:
        resolved.extend(glob.glob(g, recursive=True))
    resolved = sorted(set(resolved))[:MAX_FILES]

    # Resolve repo_root via __file__ — mode-agnostic. See spec Inv 3(e):
    # parents[0]=scripts, [1]=rabbit-spec, [2]=features, [3]=.claude, [4]=repo_root.
    # `git rev-parse` and `os.getcwd()` are forbidden here because in plugin
    # mode they resolve to the user-project root, not the rabbit root.
    repo_root = str(Path(__file__).resolve().parents[4])

    build_prompt = os.path.join(repo_root, ".claude/features/contract/scripts/build-prompt.py")

    cmd = [
        "python3", build_prompt,
        "--callable-id", "spec-create",
        "--slot", f"feature_name={args.feature_name}",
        "--slot", f"paths_globs={','.join(globs)}",
        "--slot", f"paths_resolved={chr(10).join(resolved)}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"error: build-prompt.py failed (exit {result.returncode}):", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 2

    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
