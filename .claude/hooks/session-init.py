#!/usr/bin/env python3
"""session-init.py — session-start hook.

Wired to SessionStart. Two responsibilities:

1. R1 branch enforcement (Inv 21-23, 61): if `git branch --show-current` is
   `main` or `master`, create and check out `session/YYYYMMDD-HHMMSS` and emit
   a green [rabbit] systemMessage naming the branch. Off-main: no-op.

2. Policy injection: read every @-import from CLAUDE.md and emit them as
   additionalContext so policy is present from the first prompt.

Output: one JSON object per emission, written line by line to stdout. Both
the R1 emission and the policy-injection emission MAY appear in the same
invocation (one per line).
"""

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    try:
        out = subprocess.check_output(
            ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip())
    except Exception:
        return here


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")


def _enforce_r1_branch(root: Path) -> None:
    """If on main/master, create session/YYYYMMDD-HHMMSS branch and emit msg."""
    try:
        current = subprocess.check_output(
            ["git", "-C", str(root), "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return
    if current not in ("main", "master"):
        return
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"session/{ts}"
    try:
        subprocess.check_call(
            ["git", "-C", str(root), "checkout", "-b", branch],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return
    _emit({
        "systemMessage": f"\x1b[32m🌿 ━━━ [rabbit] R1: created branch {branch} ━━━ 🌿\x1b[0m",
    })


def _inject_policy(root: Path) -> None:
    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        return

    text = claude_md.read_text()
    imports = []
    for line in text.splitlines():
        m = re.match(r"^@(\S+)", line)
        if m:
            imports.append(m.group(1))

    if not imports:
        return

    parts = [
        "Session start policy injection. Governing files from CLAUDE.md @-imports:\n\n"
    ]
    for path in imports:
        if path.startswith("/"):
            full = Path(path)
        else:
            full = root / path.lstrip("./")
        if full.is_file():
            parts.append(f"--- {path} ---\n")
            parts.append(full.read_text())
            parts.append("\n")

    payload = "".join(parts)
    files_label = " ".join(imports)
    _emit({
        "additionalContext": payload,
        "systemMessage": f"\x1b[32m✅ ━━━ [rabbit] Policy injected at session start — {files_label} ━━━ ✅\x1b[0m",
    })


def main() -> int:
    root = repo_root()
    _enforce_r1_branch(root)
    _inject_policy(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
