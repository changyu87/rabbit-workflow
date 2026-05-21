#!/usr/bin/env python3
"""session-init.py — session-start hook.

Wired to SessionStart. One responsibility:

  Policy injection: read every @-import from CLAUDE.md and emit them as
  additionalContext so policy is present from the first prompt.

Output: AT MOST ONE JSON object per invocation (Inv 85). Policy injection is
the sole pending condition; when it applies the emitted JSON carries the
policy line in systemMessage and the expanded policy text in
additionalContext. When CLAUDE.md is missing or has no @-imports, no JSON is
emitted (exit 0, empty stdout).

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
from typing import Optional


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
    welcome,
)

# BACKLOG-27 / Inv 62: canonical runtime-flag text + active-flag detection
# lives in the shared helper module so session-init.py and sync-check.py
# cannot drift. Resolve the helper from both the source dir and the build-
# managed deployed dir by walking up until features/rabbit-cage/hooks/ is
# found — symmetric with the rabbit_print discovery above. Also accept the
# sibling directly so importlib.module-loading tests resolve without
# traversing the workspace.
for _candidate in [_HERE, *_HERE.parents]:
    _maybe = _candidate / "features" / "rabbit-cage" / "hooks"
    if (_maybe / "_runtime_flags.py").is_file():
        if str(_maybe) not in sys.path:
            sys.path.insert(0, str(_maybe))
        break
else:
    if (_HERE / "_runtime_flags.py").is_file() and str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))
from _runtime_flags import active_flags, log_exc  # noqa: E402


# Inv 88 (BACKLOG-19): per-file one-liner descriptions for the welcome
# banner sub-lines. Additional @-imports introduced later show as basename
# only (no suffix).
_WELCOME_DESCRIPTIONS = {
    "philosophy.md":   "machine-first · bounded scope · designed deprecation",
    "spec-rules.md":   "determinism first; schema contracts; lifecycle ownership",
    "coding-rules.md": "think first; simplicity; surgical edits; goal-driven TDD",
}


# BACKLOG-28: log_exc is the shared helper from _runtime_flags; this tag is
# passed at each call site so the centralised helper formats the stderr
# line with the right `[session-init.py]` prefix.
_TAG = "session-init.py"


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
    except Exception as e:
        log_exc(_TAG, "repo_root: git rev-parse failed; falling back to script dir", e)
        return here


def render_policy(root: Path) -> Optional[dict]:
    """Inv 86, 88. Pure-function renderer for policy injection.

    Reads CLAUDE.md @-imports and assembles an additionalContext payload.
    Returns None when CLAUDE.md is missing or has no @-imports.
    The welcome banner is followed by per-file sub-lines that name each
    @-imported policy file along with its one-liner description (or just
    the basename if no description is registered).
    """
    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        return None

    text = claude_md.read_text()
    imports = []
    for line in text.splitlines():
        m = re.match(r"^@(\S+)", line)
        if m:
            imports.append(m.group(1))

    if not imports:
        return None

    parts = [
        "Session start policy injection. Governing files from CLAUDE.md @-imports:\n\n"
    ]
    for path in imports:
        if path.startswith("/"):
            full = Path(path)
        else:
            # BUG-59: lstrip('./') is a character-set strip; it would also
            # strip leading dots from any path starting with '.' (e.g.
            # '.claude/foo' -> 'claude/foo'). Strip a single leading './'
            # prefix only if present, then join under root.
            rel = path
            while rel.startswith("./"):
                rel = rel[2:]
            full = root / rel
        if full.is_file():
            parts.append(f"--- {path} ---\n")
            parts.append(full.read_text())
            parts.append("\n")

    payload = "".join(parts)
    # Inv 87, 88: assemble the policy block as banner + per-import sub-lines.
    # The renderer returns a SINGLE multi-line string with NO leading '\n';
    # main() wraps every payload via rabbit_block() — the sole owner of the
    # leading newline (Inv 90).
    lines = [welcome()]
    # Inv 88: pad each name so the em-dash aligns at column 17 (the longest
    # registered name `coding-rules.md` is 15 chars; +2 spaces = 17).
    PAD = 17
    for p in imports:
        name = Path(p).name
        desc = _WELCOME_DESCRIPTIONS.get(name)
        if desc:
            pad_spaces = " " * max(2, PAD - len(name))
            lines.append(rabbit_subline(f"{name}{pad_spaces}— {desc}"))
        else:
            lines.append(rabbit_subline(name))
    # Inv 62 (BACKLOG-27): append a status-flags block listing every active
    # runtime override (human-approval bypass, bypass-permissions mode, and
    # any future override added via the same per-user-marker pattern). The
    # canonical body text is shared with sync-check.py via _runtime_flags;
    # each line additionally names the revoke command so the operator sees
    # a one-line orientation per flag. When no flags are active, the block
    # is omitted entirely — no empty header, no "all clear" affirmation
    # (terse baseline banner per Inv 62).
    for flag in active_flags(root):
        lines.append(rabbit_subline(
            f"{flag['body']}  (revoke: {flag['revoke']})",
            color="red",
            icon=flag["icon"],
        ))
    return {
        "additionalContext": payload,
        "systemMessage": "\n".join(lines),
    }


def main() -> int:
    # BUG-48: surface a minimal --help so operators can introspect the hook.
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        sys.stdout.write(
            "session-init.py — SessionStart hook.\n"
            "Reads stdin (JSON payload from Claude Code, ignored) and emits "
            "CLAUDE.md @-import policy as additionalContext on stdout.\n"
            "Emits AT MOST ONE JSON object per invocation (Inv 85); policy "
            "injection is the sole pending condition.\n"
            "Takes no command-line arguments.\n"
        )
        return 0
    root = repo_root()
    payload = render_policy(root)
    if payload is None:
        return 0

    aggregated = {
        "systemMessage": rabbit_block(payload["systemMessage"]),
    }
    if "additionalContext" in payload:
        aggregated["additionalContext"] = payload["additionalContext"]

    sys.stdout.write(json.dumps(aggregated) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
