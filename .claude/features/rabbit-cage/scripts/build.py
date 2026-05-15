#!/usr/bin/env python3
"""build.py — unified workspace artifact builder.

Reads .claude/features/contract/build-contract.json and builds all declared
targets via build-targets.py.

Usage: build.py [REPO_ROOT]
"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1])
    else:
        try:
            out = subprocess.check_output(
                ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
            )
            repo_root = Path(out.decode().strip())
        except Exception:
            sys.stderr.write("build: cannot determine REPO_ROOT (not a git repo, no arg)\n")
            return 1

    contract = repo_root / ".claude/features/contract/build-contract.json"
    generate_claude_md = repo_root / ".claude/features/rabbit-cage/scripts/generate-claude-md.py"
    if not contract.exists():
        sys.stderr.write(f"build: contract not found: {contract}\n")
        return 1

    env = {**os.environ, "RABBIT_ROOT": str(repo_root)}
    cmd = [
        sys.executable,
        str(script_dir / "build-targets.py"),
        str(repo_root),
        str(contract),
        str(generate_claude_md),
    ]
    rc = subprocess.call(cmd, env=env)
    return rc


if __name__ == "__main__":
    sys.exit(main())
