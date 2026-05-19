#!/usr/bin/env python3
"""sync-check.py — Stop hook: detect policy drift in CLAUDE.md and regenerate.

Fires on Stop event. Compares the inline policy section of CLAUDE.md against
the current policy source files. If drift detected: regenerates CLAUDE.md,
emits additionalContext with the refreshed policy, and alerts the user.

Counter-gated: only checks every RABBIT_SYNC_EVERY stops (default 1).
Override in .claude/settings.local.json: {"env": {"RABBIT_SYNC_EVERY": "5"}}

Output strategy: aggregation (BACKLOG-18 / Inv 37, 38, 76). Every pending
condition contributes a [rabbit] line within a single JSON object per
invocation. Priority order controls line ORDERING (not suppression):
  1. CLAUDE.md drift (BACKLOG-19: bootstrap path REMOVED — Inv 79)
  2. Surface drift
  3. Scope-guard-off (session override or one-time-used)
  4. Human-approval-bypass
  5. Skills-updated

Brand/decoration/color/text bodies are sourced from the central registry
.claude/features/contract/schemas/rabbit-print-messages.json via the shared
renderer rabbit_print.py (Inv 18, 77).
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# Inv 77 (BACKLOG-19): import the shared renderer. Walk up from this file's
# location to find .claude/features/contract/scripts/rabbit_print.py. Works
# from both the source path (.claude/features/rabbit-cage/hooks/) and the
# build-managed copy (.claude/hooks/).
_HERE = Path(__file__).resolve().parent
for _candidate in [_HERE, *_HERE.parents]:
    _maybe = _candidate / "features" / "contract" / "scripts"
    if (_maybe / "rabbit_print.py").is_file():
        if str(_maybe) not in sys.path:
            sys.path.insert(0, str(_maybe))
        break
from rabbit_print import (  # noqa: E402
    rabbit_block,
    policy_drift, surface_drift,
    scope_guard_off, scope_guard_bypassed,
    human_approval_bypass, skills_updated,
)


def _log_exc(where: str, exc: BaseException) -> None:
    """BACKLOG-17 / Inv 70: log unexpected exceptions to stderr instead of
    silently swallowing them. Hooks keep their exit-0 happy-path contract,
    but failures are now visible to operators inspecting the transcript."""
    try:
        sys.stderr.write(f"[sync-check.py] {where}: {type(exc).__name__}: {exc}\n")
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


# Inv 63: additionalContext MUST either expand @-imports or carry a clear
# note that the agent must independently load referenced files.
AT_IMPORT_NOTE = (
    "NOTE: @-imports in the section below are NOT auto-resolved inside "
    "additionalContext. The agent MUST independently Read each "
    "referenced file (e.g. `Read('.claude/policy/<file>.md')`) to load "
    "the actual policy content.\n\n"
)


def _policy_section(text: str) -> str:
    m = re.search(
        r"(?m)^.*rabbit-policy-start.*$.*?(?:^.*rabbit-policy-end.*$)",
        text,
        re.DOTALL,
    )
    return m.group(0) if m else ""


def _wrap_ctx(section: str, full: str) -> str:
    body = section + "\n" if section else full
    return AT_IMPORT_NOTE + body


def render_claude_md_drift(root: Path, expected: str) -> Optional[dict]:
    """Inv 17, 38, 76, 79. Renders CLAUDE.md drift condition.

    BACKLOG-19 / Inv 79: the missing-CLAUDE.md path was removed; in any real
    checkout CLAUDE.md is committed. If CLAUDE.md is genuinely missing, this
    renderer returns None (silent) — bootstrap is install.py's responsibility.
    """
    claude_md = root / "CLAUDE.md"
    refresh_every = os.environ.get("RABBIT_REFRESH_EVERY", "20")

    if not claude_md.exists():
        return None

    if claude_md.read_text() != expected:
        claude_md.write_text(expected)
        (root / ".rabbit-prompt-counter").write_text(f"{refresh_every}\n")
        section = _policy_section(expected)
        return {
            "additionalContext": _wrap_ctx(section, expected),
            "systemMessage": policy_drift(),
        }

    return None


def _collect_drifted_targets(root: Path) -> list:
    """Inv 78 (BACKLOG-21). Compare each copy-file target's source and
    destination by sha256; return the NAMES of the drifted targets.

    Only check_on_stop=true copy-file targets are considered. Missing source
    files are skipped (build.py is the authority on bootstrap, not the
    drift detector). A missing destination counts as drift.
    """
    contract_path = root / ".claude/features/contract/build-contract.json"
    try:
        data = json.loads(contract_path.read_text())
    except Exception as e:
        _log_exc("failed to read build-contract.json", e)
        return []
    drifted = []
    for target in data.get("targets", []):
        if target.get("type") != "copy-file":
            continue
        if not target.get("check_on_stop"):
            continue
        src = root / target["source"]
        dst = root / target["destination"]
        if not src.is_file():
            continue
        try:
            src_sha = hashlib.sha256(src.read_bytes()).hexdigest()
        except Exception as e:
            _log_exc(f"failed to hash source for {target.get('name')}", e)
            continue
        if dst.is_file():
            try:
                dst_sha = hashlib.sha256(dst.read_bytes()).hexdigest()
            except Exception as e:
                _log_exc(f"failed to hash destination for {target.get('name')}", e)
                continue
            if src_sha != dst_sha:
                drifted.append(target["name"])
        else:
            drifted.append(target["name"])
    return drifted


def render_surface_drift(root: Path) -> Optional[dict]:
    """Inv 38, 76, 78 (BACKLOG-21). Render surface-drift condition.

    Iterates build-contract.json copy-file targets, collects the names of
    those whose destination sha256 diverges from the source, then invokes
    build.py to rebuild. The user-visible message names exactly which
    targets were rebuilt.
    """
    drifted = _collect_drifted_targets(root)
    if not drifted:
        return None
    build_py = root / ".claude/features/rabbit-cage/scripts/build.py"
    try:
        subprocess.call(
            [str(build_py), str(root)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        _log_exc("build.py invocation failed during surface-drift rebuild", e)
    return {
        "systemMessage": surface_drift(files=", ".join(drifted)),
    }


def render_scope_guard(root: Path) -> Optional[dict]:
    """Inv 38, 76. Render scope-guard-off condition.

    Two sub-states: session override active (persistent) or one-time
    override consumed (consume-on-read of .rabbit-scope-override-used).
    """
    override_file = root / ".rabbit-scope-override"
    used_file = root / ".rabbit-scope-override-used"
    alert = ""
    if override_file.is_file():
        try:
            mode = "".join(c for c in override_file.read_text() if not c.isspace())
        except Exception as e:
            _log_exc("could not read .rabbit-scope-override", e)
            mode = ""
        if mode == "session":
            alert = "session"
    if used_file.is_file():
        alert = "used"
        try:
            used_file.unlink()
        except Exception as e:
            _log_exc("could not unlink .rabbit-scope-override-used", e)

    if alert == "session":
        return {
            "systemMessage": scope_guard_off(),
        }
    if alert == "used":
        return {
            "systemMessage": scope_guard_bypassed(),
        }
    return None


def render_human_approval(root: Path) -> Optional[dict]:
    """Inv 59, 76. Render human-approval-bypass alert. Persistent marker;
    not consumed on read."""
    marker = root / ".rabbit-human-approval-bypass"
    if not marker.is_file():
        return None
    return {
        "systemMessage": human_approval_bypass(),
    }


def render_skills_updated(root: Path) -> Optional[dict]:
    """Inv 24, 76. Render skills-updated alert. Consume-on-read of
    .rabbit-skills-updated."""
    marker = root / ".rabbit-skills-updated"
    if not marker.is_file():
        return None
    try:
        content = marker.read_text()
    except Exception as e:
        _log_exc("could not read .rabbit-skills-updated", e)
        content = ""
    names = ",".join(ln for ln in content.splitlines() if ln).rstrip(",")
    try:
        marker.unlink()
    except Exception as e:
        _log_exc("could not unlink .rabbit-skills-updated", e)
    return {
        "systemMessage": skills_updated(names=names),
    }


def main() -> int:
    # BUG-48: surface a minimal --help so operators can introspect the hook.
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        sys.stdout.write(
            "sync-check.py — Stop hook.\n"
            "Detects CLAUDE.md / surface drift, scope-guard override state, "
            "human-approval bypass, and skill updates; emits at most one JSON "
            "object to stdout per invocation (aggregation strategy — every "
            "pending condition contributes a rendered banner line, ordered by "
            "Inv 37 priority).\n"
            "Takes no command-line arguments.\n"
        )
        return 0
    root = repo_root()
    generate_script = root / ".claude/features/rabbit-cage/scripts/generate-claude-md.py"
    counter_file = root / ".rabbit-sync-counter"
    threshold = int(os.environ.get("RABBIT_SYNC_EVERY", "1"))

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

    # Generate expected CLAUDE.md. Narrow except to the specific failure modes
    # (missing/unexecutable generator script or non-zero exit) so we do not
    # silently mask programming errors elsewhere (BUG-47).
    try:
        expected = subprocess.check_output(
            [str(generate_script)],
            stderr=subprocess.DEVNULL,
            env={**os.environ, "RABBIT_ROOT": str(root)},
        ).decode()
    except (FileNotFoundError, PermissionError, subprocess.CalledProcessError, OSError):
        return 0

    # Inv 37 priority order: invoke each renderer in turn, collect non-None
    # payloads. The renderer is responsible for any consume-on-read side
    # effect (markers) when the condition applies.
    payloads = []
    for payload in (
        render_claude_md_drift(root, expected),
        render_surface_drift(root),
        render_scope_guard(root),
        render_human_approval(root),
        render_skills_updated(root),
    ):
        if payload is not None:
            payloads.append(payload)

    if not payloads:
        return 0

    aggregated = {
        "systemMessage": rabbit_block(*(p["systemMessage"] for p in payloads)),
    }
    # additionalContext: only render_claude_md_drift emits one today; take
    # the first if present (Inv 38).
    for p in payloads:
        if "additionalContext" in p:
            aggregated["additionalContext"] = p["additionalContext"]
            break

    sys.stdout.write(json.dumps(aggregated) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
