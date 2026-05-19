"""rabbit_print.py — shared renderer for the [rabbit] print convention.

Loads the message registry from
.claude/features/contract/schemas/rabbit-print-messages.json on first use
and caches it for the lifetime of the process. Producers (rabbit-cage hooks,
tdd-subagent scripts) import this module and call the two public functions
to compose ANSI-colored output strings. The module itself does not write to
stdout or stderr — it returns strings only.

Public API:
    rabbit_print(message_id, **kwargs) -> str
    rabbit_subline(text, color="green") -> str

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the [rabbit] print convention is replaced by a
    structured logging facility
"""

import json
from pathlib import Path

__all__ = ["rabbit_print", "rabbit_subline"]

_CACHE = {}
_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "schemas" / "rabbit-print-messages.json"


def _load():
    if "reg" not in _CACHE:
        with open(_REGISTRY_PATH) as f:
            _CACHE["reg"] = json.load(f)
    return _CACHE["reg"]


def rabbit_print(message_id, **kwargs):
    """Compose a fully-formed [rabbit] banner line for message_id.

    Returns the string:
        f"{ansi}{brand} {icon} {bar} {text} {bar} {icon}{reset}"
    where text has {name} placeholders substituted from kwargs.

    Raises KeyError if message_id is not in the registry, or if a required
    {name} placeholder is missing from kwargs.
    """
    reg = _load()
    m = reg["messages"][message_id]
    c = reg["colors"][m["color"]]
    body = m["text"].format(**kwargs)
    brand = reg["brand"]
    bar = reg["bar"]
    icon = m["icon"]
    return f"{c['ansi']}{brand} {icon} {bar} {body} {bar} {icon}{c['reset']}"


def rabbit_subline(text, color="green"):
    """Compose a sub-line (brand prefix + free text) in the given color.

    Returns the string:
        f"{ansi}{brand} {text}{reset}"
    """
    reg = _load()
    c = reg["colors"][color]
    return f"{c['ansi']}{reg['brand']} {text}{c['reset']}"
