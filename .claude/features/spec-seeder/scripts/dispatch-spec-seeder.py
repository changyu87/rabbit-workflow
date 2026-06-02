#!/usr/bin/env python3
"""dispatch-spec-seeder.py — assemble the spec-seeder subagent prompt.

Used by rabbit-feature-new in plugin mode when a user declares a new feature
mapping. Resolves the declared path globs, caps the resolved file list at 50
entries, and invokes contract/scripts/build-prompt.py to assemble the prompt.

Usage:
    dispatch-spec-seeder.py --feature-name <name> --paths <glob1>,<glob2>,...

Prints the absolute path of the assembled prompt file to stdout on success.

Exit codes:
    0 = success
    1 = invocation error (missing args, glob resolution failure)
    2 = build-prompt.py subprocess failure

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit's per-project plugin model is superseded
"""

import argparse
import glob
import os
import subprocess
import sys

MAX_FILES = 50


def main():
    parser = argparse.ArgumentParser(description="Dispatch the spec-seeder subagent prompt")
    parser.add_argument("--feature-name", required=True, help="Feature name (kebab-case)")
    parser.add_argument("--paths", required=True, help="Comma-separated path globs")
    args = parser.parse_args()

    globs = [g.strip() for g in args.paths.split(",") if g.strip()]
    if not globs:
        print("error: --paths must contain at least one non-empty glob", file=sys.stderr)
        return 1

    resolved = []
    for g in globs:
        resolved.extend(glob.glob(g, recursive=True))
    resolved = sorted(set(resolved))[:MAX_FILES]

    repo_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() or os.getcwd()

    build_prompt = os.path.join(repo_root, ".claude/features/contract/scripts/build-prompt.py")

    cmd = [
        "python3", build_prompt,
        "--callable-id", "spec-seeder",
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
