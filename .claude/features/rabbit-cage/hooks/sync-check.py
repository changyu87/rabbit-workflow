#!/usr/bin/env python3
"""sync-check.py — Stop hook: detect policy drift in CLAUDE.md and regenerate.

Fires on Stop event. Compares the inline policy section of CLAUDE.md against
the current policy source files. If drift detected: regenerates CLAUDE.md,
emits additionalContext with the refreshed policy, and alerts the user.

Counter-gated: only checks every RABBIT_SYNC_EVERY stops (default 1).
Override in .claude/settings.local.json: {"env": {"RABBIT_SYNC_EVERY": "5"}}

Output strategy: conditional-priority (at most one JSON object per invocation).
Priority order: CLAUDE.md drift/first-run > surface drift > scope-guard-off > skills-updated.
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


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")


def main() -> int:
    root = repo_root()
    claude_md = root / "CLAUDE.md"
    generate_script = root / ".claude/features/rabbit-cage/scripts/generate-claude-md.py"
    counter_file = root / ".rabbit-sync-counter"
    threshold = int(os.environ.get("RABBIT_SYNC_EVERY", "1"))
    refresh_every = os.environ.get("RABBIT_REFRESH_EVERY", "20")

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
    counter_file.write_text("0\n")

    # Generate expected CLAUDE.md
    try:
        expected = subprocess.check_output(
            [str(generate_script)],
            stderr=subprocess.DEVNULL,
            env={**os.environ, "RABBIT_ROOT": str(root)},
        ).decode()
    except Exception:
        return 0

    def policy_section(text: str) -> str:
        m = re.search(
            r"(?m)^.*rabbit-policy-start.*$.*?(?:^.*rabbit-policy-end.*$)",
            text,
            re.DOTALL,
        )
        return m.group(0) if m else ""

    # First-run scenario
    if not claude_md.exists():
        claude_md.write_text(expected)
        (root / ".rabbit-prompt-counter").write_text(f"{refresh_every}\n")
        section = policy_section(expected)
        emit({
            "additionalContext": section + "\n" if section else expected,
            "systemMessage": "\x1b[32m📋 ━━━ [rabbit] Policy initialized — CLAUDE.md created for first time ━━━ 📋\x1b[0m",
        })
        return 0

    # Drift scenario
    if claude_md.read_text() != expected:
        claude_md.write_text(expected)
        (root / ".rabbit-prompt-counter").write_text(f"{refresh_every}\n")
        section = policy_section(expected)
        emit({
            "additionalContext": section + "\n" if section else expected,
            "systemMessage": "\x1b[31m⚠️ ━━━ [rabbit] Policy drift detected — CLAUDE.md regenerated from source files ━━━ ⚠️\x1b[0m",
        })
        return 0

    json_emitted = False

    # Surface drift check (calls test-generated-surface.py; rebuilds via build.py)
    test_surface = root / ".claude/features/rabbit-cage/test/test-generated-surface.py"
    build_py = root / ".claude/features/rabbit-cage/scripts/build.py"
    if test_surface.is_file():
        rc = subprocess.call(
            [sys.executable, str(test_surface)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if rc != 0:
            try:
                subprocess.call(
                    [str(build_py), str(root)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
            emit({
                "systemMessage": "\x1b[32m🔄 ━━━ [rabbit] Surface drift detected — workspace rebuilt from sources ━━━ 🔄\x1b[0m",
            })
            json_emitted = True

    # Scope-guard override alert
    override_file = root / ".rabbit-scope-override"
    used_file = root / ".rabbit-scope-override-used"
    alert = ""
    if override_file.is_file():
        try:
            mode = "".join(c for c in override_file.read_text() if not c.isspace())
        except Exception:
            mode = ""
        if mode == "session":
            alert = "session"
    if used_file.is_file():
        alert = "used"
        try:
            used_file.unlink()
        except Exception:
            pass

    if not json_emitted:
        if alert == "session":
            emit({
                "systemMessage": "\x1b[31m🔓 ━━━ [rabbit] SCOPE GUARD OFF (session override active) ━━━ 🔓\x1b[0m",
            })
            json_emitted = True
        elif alert == "used":
            emit({
                "systemMessage": "\x1b[31m🔓 ━━━ [rabbit] SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed) ━━━ 🔓\x1b[0m",
            })
            json_emitted = True

    # Skills-updated marker
    skills_marker = root / ".rabbit-skills-updated"
    if skills_marker.is_file() and not json_emitted:
        try:
            content = skills_marker.read_text()
        except Exception:
            content = ""
        names = ",".join(ln for ln in content.splitlines() if ln).rstrip(",")
        try:
            skills_marker.unlink()
        except Exception:
            pass
        emit({
            "systemMessage": f"\x1b[32m[rabbit] Skills updated: {names} — will reload automatically on next invocation.\x1b[0m",
        })

    return 0


if __name__ == "__main__":
    sys.exit(main())
