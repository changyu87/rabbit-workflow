#!/usr/bin/env python3
"""refresh.py — periodic re-injection of CLAUDE.md @-imports.

Wired to UserPromptSubmit. Each prompt: increment counter; if counter
reaches RABBIT_REFRESH_EVERY (default 20), emit JSON additionalContext
containing the full content of every file that CLAUDE.md @-imports,
then reset the counter to 0.

Stays silent (exits 0 with no stdout) when not refreshing.
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
    counter_file = root / ".rabbit-prompt-counter"
    threshold = int(os.environ.get("RABBIT_REFRESH_EVERY", "20"))

    if not counter_file.exists():
        counter_file.write_text("0\n")

    try:
        count = int(counter_file.read_text().strip() or "0")
    except ValueError:
        count = 0
    count += 1

    if count < threshold:
        counter_file.write_text(f"{count}\n")
        return 0

    # Threshold reached: gather @-imports, emit additionalContext
    counter_file.write_text("0\n")

    if not claude_md.exists():
        return 0

    text = claude_md.read_text()

    # BUG-80: inline rabbit-policy-start/rabbit-policy-end section detection
    # removed — generate-claude-md.py no longer emits those markers, so this
    # branch was dead code.

    # Parse @-imports: lines starting with '@'
    imports = []
    for line in text.splitlines():
        m2 = re.match(r"^@(\S+)", line)
        if m2:
            imports.append(m2.group(1))

    if not imports:
        return 0

    parts = [
        f"Periodic policy refresh (every {threshold} prompts). Re-stating governing files:\n\n"
    ]
    for path in imports:
        if path.startswith("/"):
            full = Path(path)
        else:
            # BUG-59: lstrip('./') is a character-set strip and would also
            # strip leading dots from '.claude/foo'. Strip a single leading
            # './' prefix only if present, then join under root.
            rel = path
            while rel.startswith("./"):
                rel = rel[2:]
            full = root / rel
        if full.is_file():
            parts.append(f"--- {path} ---\n")
            parts.append(full.read_text())
            parts.append("\n")

    payload = "".join(parts)
    # BACKLOG-7: per-file bullet lines (one file per line) instead of a single
    # space-joined dense list. Border chars and emoji preserved (Inv 18 + the
    # BACKLOG-7-visual-messages contract).
    files_label = "\n  · " + "\n  · ".join(imports)
    print(json.dumps({
        "additionalContext": payload,
        "systemMessage": (
            f"\x1b[32m🔄 ━━━ [rabbit] Policy refreshed ━━━ 🔄"
            f"{files_label}\x1b[0m"
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
