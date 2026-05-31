#!/usr/bin/env python3
"""session-start-dispatcher.py — Claude Code SessionStart hook dispatcher.

Enumerates every active feature's `feature.json runtime.SessionStart`
declarations, invokes each declared API via `contract.lib.runtime`,
partitions returns into print/inject/ok/error, and emits at most one
JSON object to stdout.

Inv 20 (plugin-mode RABBIT_ROOT check): when running in plugin mode
(detected by presence of <install_root>/.version), appends a banner
payload to the dispatch result if RABBIT_ROOT is unset or mismatched.

Version: 1.1.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when Claude Code exposes native SessionStart
    dispatchers that subsume this hook.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from _dispatcher_lib import dispatch_event, render_emission  # noqa: E402


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


def _check_rabbit_root_env():
    """Inv 20: in plugin mode, return banner payload if RABBIT_ROOT env
    is unset or does not match the expected install root. Returns None
    in standalone mode (no .version file) or when env matches.
    """
    install_root = Path(__file__).resolve().parent.parent.parent
    if not (install_root / ".version").is_file():
        return None
    actual = os.environ.get("RABBIT_ROOT", "")
    expected = str(install_root)
    if actual == expected:
        return None
    text = (
        f"RABBIT_ROOT not set or mismatched. Expected: {expected}\n"
        "Exit Claude, run one of:\n"
        f"    setenv RABBIT_ROOT {expected}   (tcsh)\n"
        f"    export RABBIT_ROOT={expected}   (bash/zsh)\n"
        "Then relaunch Claude."
    )
    return {"type": "banner", "text": text, "icon": "🚨", "color": "red"}


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        sys.stdout.write(
            "session-start-dispatcher.py — Claude Code SessionStart hook.\n"
            "Enumerates every active feature's runtime.SessionStart declarations, "
            "invokes each via contract.lib.runtime, emits at most one JSON "
            "object to stdout.\n"
        )
        return 0
    try:
        sys.stdin.read()
    except Exception:
        pass
    root = str(repo_root())
    payloads = dispatch_event("SessionStart", root)
    alert = _check_rabbit_root_env()
    if alert is not None:
        payloads.append(alert)
    emission = render_emission(payloads)
    if emission is not None:
        sys.stdout.write(json.dumps(emission) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
