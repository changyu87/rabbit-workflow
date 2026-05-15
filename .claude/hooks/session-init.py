#!/usr/bin/env python3
"""session-init.py — session-start injection of CLAUDE.md @-imports.

Wired to SessionStart. Fires immediately at session start (no counter gate).
Reads all @-import paths from CLAUDE.md and emits them as additionalContext
JSON so policy is present from the very first prompt.

Output format: {"additionalContext": "...", "systemMessage": "..."}
Stays silent (exits 0 with no stdout) if no @-imports found in CLAUDE.md.
"""

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


def main() -> int:
    root = repo_root()
    claude_md = root / "CLAUDE.md"

    if not claude_md.exists():
        return 0

    text = claude_md.read_text()
    imports = []
    for line in text.splitlines():
        m = re.match(r"^@(\S+)", line)
        if m:
            imports.append(m.group(1))

    if not imports:
        return 0

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
    print(json.dumps({
        "additionalContext": payload,
        "systemMessage": f"\x1b[32m✅ ━━━ [rabbit] Policy injected at session start — {files_label} ━━━ ✅\x1b[0m",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
