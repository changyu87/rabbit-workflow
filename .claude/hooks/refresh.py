#!/usr/bin/env python3
"""refresh.py — periodic re-injection of CLAUDE.md @-imports.

Wired to UserPromptSubmit. Each prompt: increment counter; if counter
reaches RABBIT_REFRESH_EVERY (default 20), emit JSON additionalContext
containing the full content of every file that CLAUDE.md @-imports,
then reset the counter to 0.

Stays silent (exits 0 with no stdout) when not refreshing.

Brand/decoration/color/text bodies are sourced from the central registry
.claude/features/contract/schemas/rabbit-print-messages.json via the shared
renderer rabbit_print.py (Inv 73, 87).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


# Inv 87 (BACKLOG-19): import the shared renderer. See sync-check.py for
# the symmetric path-discovery rationale.
_HERE = Path(__file__).resolve().parent
for _candidate in [_HERE, *_HERE.parents]:
    _maybe = _candidate / "features" / "contract" / "scripts"
    if (_maybe / "rabbit_print.py").is_file():
        if str(_maybe) not in sys.path:
            sys.path.insert(0, str(_maybe))
        break
from rabbit_print import (  # noqa: E402
    rabbit_block, rabbit_subline,
    policy_refreshed,
)


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
    # Inv 87, 90: assemble via rabbit_block — the sole owner of the leading
    # newline. BACKLOG-20 missed refresh.py; this picks it up.
    banner = policy_refreshed()
    print(json.dumps({
        "additionalContext": payload,
        "systemMessage": rabbit_block(banner, *(rabbit_subline(p) for p in imports)),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
