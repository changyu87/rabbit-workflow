#!/usr/bin/env python3
"""session-init.py — session-start hook.

Wired to SessionStart. Two responsibilities:

1. R1 branch enforcement (Inv 21-23, 61): if `git branch --show-current` is
   `main` or `master`, create and check out `session/YYYYMMDD-HHMMSS` and emit
   a green [rabbit] systemMessage naming the branch. Off-main: no-op.

2. Policy injection: read every @-import from CLAUDE.md and emit them as
   additionalContext so policy is present from the first prompt.

Output: AT MOST ONE JSON object per invocation (Inv 75 / BACKLOG-18). When
both conditions apply, their rendered [rabbit] lines are combined into one
systemMessage (newline-joined, R1 line first, policy line second) and
emitted within a single JSON object that also carries additionalContext
when policy injection applies.

Brand/decoration/color/text bodies are sourced from the central registry
.claude/features/contract/schemas/rabbit-print-messages.json via the shared
renderer rabbit_print.py (Inv 18, 77).
"""

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# Inv 77 (BACKLOG-19): import the shared renderer. See sync-check.py for
# the symmetric path-discovery rationale.
_HERE = Path(__file__).resolve().parent
for _candidate in [_HERE, *_HERE.parents]:
    _maybe = _candidate / "features" / "contract" / "scripts"
    if (_maybe / "rabbit_print.py").is_file():
        if str(_maybe) not in sys.path:
            sys.path.insert(0, str(_maybe))
        break
from rabbit_print import rabbit_print, rabbit_subline  # noqa: E402


# Inv 78 (BACKLOG-19): per-file one-liner descriptions for the welcome
# banner sub-lines. Additional @-imports introduced later show as basename
# only (no suffix).
_WELCOME_DESCRIPTIONS = {
    "philosophy.md":   "machine-first · bounded scope · designed deprecation",
    "spec-rules.md":   "determinism first; schema contracts; lifecycle ownership",
    "coding-rules.md": "think first; simplicity; surgical edits; goal-driven TDD",
}


def _log_exc(where: str, exc: BaseException) -> None:
    """BACKLOG-17 / Inv 70: log unexpected exceptions to stderr instead of
    silently swallowing them. Hook keeps its exit-0 happy-path contract."""
    try:
        sys.stderr.write(f"[session-init.py] {where}: {type(exc).__name__}: {exc}\n")
    except Exception:
        pass


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
        _log_exc("repo_root: git rev-parse failed; falling back to script dir", e)
        return here


def render_r1_branch(root: Path) -> Optional[dict]:
    """Inv 21-23, 61, 76. Pure-function renderer for R1 branch enforcement.

    If currently on main/master, create session/YYYYMMDD-HHMMSS branch (side
    effect: git checkout -b) and return the alert payload. Off-main: return
    None and do nothing.
    """
    try:
        current = subprocess.check_output(
            ["git", "-C", str(root), "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception as e:
        _log_exc("git branch --show-current failed; skipping R1 enforcement", e)
        return None
    if current not in ("main", "master"):
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"session/{ts}"
    try:
        subprocess.check_call(
            ["git", "-C", str(root), "checkout", "-b", branch],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        _log_exc(f"git checkout -b {branch} failed; R1 branch not created", e)
        return None
    return {
        "systemMessage": rabbit_print("r1-branch", branch=branch),
    }


def render_policy(root: Path) -> Optional[dict]:
    """Inv 76, 78. Pure-function renderer for policy injection.

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
    banner = rabbit_print("welcome")
    sublines = []
    # Inv 78: pad each name so the em-dash aligns at column 17 (the longest
    # registered name `coding-rules.md` is 15 chars; +2 spaces = 17).
    PAD = 17
    for p in imports:
        name = Path(p).name
        desc = _WELCOME_DESCRIPTIONS.get(name)
        if desc:
            pad_spaces = " " * max(2, PAD - len(name))
            sublines.append(rabbit_subline(f"{name}{pad_spaces}— {desc}"))
        else:
            sublines.append(rabbit_subline(name))
    return {
        "additionalContext": payload,
        "systemMessage": banner + "\n" + "\n".join(sublines),
    }


def main() -> int:
    # BUG-48: surface a minimal --help so operators can introspect the hook.
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        sys.stdout.write(
            "session-init.py — SessionStart hook.\n"
            "Reads stdin (JSON payload from Claude Code, ignored), enforces R1 "
            "branch policy, and emits CLAUDE.md @-import policy as "
            "additionalContext on stdout.\n"
            "Emits AT MOST ONE JSON object per invocation (Inv 75); R1 and "
            "policy lines are aggregated into one systemMessage when both apply.\n"
            "Takes no command-line arguments.\n"
        )
        return 0
    root = repo_root()
    payloads = []
    for payload in (render_r1_branch(root), render_policy(root)):
        if payload is not None:
            payloads.append(payload)

    if not payloads:
        return 0

    aggregated = {
        "systemMessage": "\n" + "\n".join(p["systemMessage"] for p in payloads),
    }
    for p in payloads:
        if "additionalContext" in p:
            aggregated["additionalContext"] = p["additionalContext"]
            break

    sys.stdout.write(json.dumps(aggregated) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
