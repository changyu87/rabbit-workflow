#!/usr/bin/env python3
# check-symlinks-resolve.py — assert every symlink under .claude/ resolves to an
# existing file or directory (no dangling symlinks).
#
# Usage: check-symlinks-resolve.py [repo-root]
# Exit:  0 all symlinks resolve (or none found); 1 dangling symlinks found.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when symlink validation is provided by a native linter.

import os
import subprocess
import sys


def get_repo_root():
    env_root = os.environ.get("RABBIT_ROOT")
    if env_root:
        return env_root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def main():
    if len(sys.argv) > 1:
        repo_root = sys.argv[1]
    else:
        repo_root = get_repo_root()

    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        sys.exit(2)

    claude_dir = os.path.join(repo_root, ".claude")
    if not os.path.isdir(claude_dir):
        print(f"OK: no .claude/ at {repo_root} (vacuous)")
        sys.exit(0)

    dangling = []
    # Walk with maxdepth=3 equivalent: only go 3 levels deep
    for dirpath, dirnames, filenames in os.walk(claude_dir):
        depth = dirpath[len(claude_dir):].count(os.sep)
        if depth >= 3:
            dirnames.clear()
            continue

        for fname in filenames + dirnames:
            full = os.path.join(dirpath, fname)
            if os.path.islink(full):
                target = os.path.realpath(full)
                if not target or not os.path.exists(target):
                    dangling.append(full)

    if dangling:
        for link in sorted(dangling):
            print(f"DANGLING: {link}", file=sys.stderr)
        print(f"FAIL: dangling symlinks found under {repo_root}/.claude", file=sys.stderr)
        sys.exit(1)

    print("OK: all symlinks under .claude/ resolve")
    sys.exit(0)


if __name__ == "__main__":
    main()
