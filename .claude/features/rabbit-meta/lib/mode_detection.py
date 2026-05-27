"""mode_detection — detect whether rabbit is running in plugin or standalone mode.

Inv 1 of the rabbit-meta feature. Pure stdlib; no side effects, no env reads,
no logging.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: inherits from rabbit-meta feature deprecation
    (when rabbit's per-project plugin model is superseded by a native
    Claude Code workflow contract mechanism).
"""

import os


def detect_mode(cwd: str) -> str:
    """Return "plugin" if cwd is a `.rabbit/` directory vendored into a host
    project, else "standalone".

    Plugin signature: basename(cwd) == ".rabbit" AND dirname(cwd) exists AND
    that parent contains at least one entry whose name is not ".rabbit".
    Any filesystem error (missing path, permission, etc.) returns "standalone"
    as a safe default; the function MUST NOT raise.
    """
    try:
        entries = os.listdir(os.path.dirname(cwd))
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return "standalone"
    if os.path.basename(cwd) == ".rabbit" and any(name != ".rabbit" for name in entries):
        return "plugin"
    return "standalone"
