#!/usr/bin/env python3
# check-imports-resolve.py — assert every @<path> import and .claude/features/<name>
# path reference in docs/ .md files resolves to an existing filesystem path.
#
# Usage: check-imports-resolve.py <feature-dir>
# Exit:  0 all paths resolve (or no docs/); 1 one or more missing paths.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when import resolution is enforced by a native linter.

import os
import re
import subprocess
import sys


def get_repo_root():
    env_root = os.environ.get("RABBIT_ROOT")
    if env_root:
        return env_root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        result = subprocess.run(
            ["git", "-C", script_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def main():
    if len(sys.argv) < 2:
        print("usage: check-imports-resolve.py <feature-dir>", file=sys.stderr)
        sys.exit(2)

    feature_dir = sys.argv[1]
    docs_dir = os.path.join(feature_dir, "docs")

    if not os.path.isdir(docs_dir):
        print(f"OK: no docs/ in {feature_dir} (vacuous)")
        sys.exit(0)

    repo_root = get_repo_root()
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        sys.exit(2)

    fail = 0

    # Find all .md files under docs/
    md_files = []
    for root, dirs, files in os.walk(docs_dir):
        for fname in files:
            if fname.endswith(".md"):
                md_files.append(os.path.join(root, fname))

    at_rel_pattern = re.compile(r'@\./([^\s]+)')
    claude_path_pattern = re.compile(r'\.claude/features/[a-z][a-z0-9-]+(?:/[^\s)\]\']+)?')

    for filepath in md_files:
        # Skip archive/ directories
        if "/archive/" in filepath:
            continue

        with open(filepath) as f:
            content = f.read()

        # Extract @./ imports
        for match in at_rel_pattern.finditer(content):
            path = match.group(1)
            if "{{" in path:
                continue
            full = os.path.join(repo_root, path)
            if not os.path.exists(full):
                print(f"MISSING: {path} (in {filepath})", file=sys.stderr)
                fail = 1

        # Extract .claude/features/<name> paths
        for match in claude_path_pattern.finditer(content):
            path = match.group(0)
            if "{{" in path:
                continue
            full = os.path.join(repo_root, path)
            if not os.path.exists(full):
                print(f"MISSING: {path} (in {filepath})", file=sys.stderr)
                fail = 1

    if fail:
        print("FAIL: one or more import/path references are missing", file=sys.stderr)
        sys.exit(1)

    print("OK: all import and feature path references resolve")
    sys.exit(0)


if __name__ == "__main__":
    main()
