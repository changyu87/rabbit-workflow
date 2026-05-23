"""contract.lib.runtime — API library for the runtime APIs invoked by the
per-event dispatcher hooks (Stop, SessionStart, UserPromptSubmit). Each
function implements one runtime API call declared in a feature's RUNTIME
section and returns one or more typed result dicts.

Return-type vocabulary (built via the four factory helpers below):
    print   {"type": "print",  "text": str, "icon": str, "color": str}
    inject  {"type": "inject", "content": str}
    ok      {"type": "ok"}
    error   {"type": "error", "message": str}

Functions that may emit both a print and an inject return a list of two
results in [print, inject] order. The single-result APIs return one dict.
The iterate_configurables_* APIs always return a (possibly empty) list of
print results.

Path-arg convention: every path arg accepted by these APIs is repo-root-
relative unless explicitly noted. (This differs from lib.producers, which
resolves relative paths against feature_dir.)

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the rabbit CLI exposes native per-event
    dispatchers that subsume this library.
"""

import os


def print_result(text: str, icon: str, color: str) -> dict:
    """Tagged dict for an alert line that the dispatcher renders via
    rabbit_print and joins into the Stop hook systemMessage."""
    return {"type": "print", "text": text, "icon": icon, "color": color}


def inject_result(content: str) -> dict:
    """Tagged dict for additional context the dispatcher attaches to the
    Stop/SessionStart/UserPromptSubmit additionalContext field."""
    return {"type": "inject", "content": content}


def ok_result() -> dict:
    """Tagged dict for the no-op case — dispatcher drops these."""
    return {"type": "ok"}


def error_result(message: str) -> dict:
    """Tagged dict for an internal failure — dispatcher logs to stderr and
    does NOT surface to Claude."""
    return {"type": "error", "message": message}


def check_marker_alert(path: str, content, alert: dict, *, repo_root: str) -> dict:
    """If the marker at `path` (repo-root-relative) exists, return a print
    result built from `alert` ({text, icon, color}). If `content` is not
    None, the marker file must also contain exactly that string; otherwise
    treat as absent.
    """
    full = os.path.join(repo_root, path)
    if not os.path.isfile(full):
        return ok_result()
    if content is not None:
        try:
            with open(full) as f:
                if f.read() != content:
                    return ok_result()
        except OSError:
            return ok_result()
    return print_result(alert["text"], alert["icon"], alert["color"])
