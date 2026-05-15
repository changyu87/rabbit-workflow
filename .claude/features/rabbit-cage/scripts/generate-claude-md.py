#!/usr/bin/env python3
"""generate-claude-md.py — generate CLAUDE.md header + @-import pointers.

Reads the header line from policy-header.json; emits a CLAUDE.md that uses
@-import pointers to the four policy files (no inline policy content).

Usage:
  generate-claude-md.py                    # emit to stdout
  generate-claude-md.py --write [TARGET]   # write to TARGET/CLAUDE.md (default: REPO_ROOT)
"""

import os
import subprocess
import sys
from pathlib import Path


def repo_root(start: Path) -> Path:
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return Path(env)
    try:
        out = subprocess.check_output(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip())
    except Exception:
        return start.parent


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    rroot = repo_root(script_dir)
    policy_header_json = script_dir.parent / "policy-header.json"

    write_mode = False
    target_root = rroot
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--write":
            write_mode = True
            if i + 1 < len(args):
                target_root = Path(args[i + 1])
                i += 2
            else:
                i += 1
        else:
            sys.stderr.write(f"ERROR: unknown arg '{a}'\n")
            return 2

    header = subprocess.check_output(
        [sys.executable, str(script_dir / "generate-claude-md-header.py"), str(policy_header_json)]
    ).decode().rstrip("\n")

    body = (
        f"{header}\n"
        "\n"
        "@.claude/features/policy/philosophy.md\n"
        "@.claude/features/policy/spec-rules.md\n"
        "@.claude/features/policy/coding-rules.md\n"
    )

    if write_mode:
        target_root.mkdir(parents=True, exist_ok=True)
        (target_root / "CLAUDE.md").write_text(body)
        sys.stderr.write(f"generate-claude-md: wrote {target_root}/CLAUDE.md\n")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
