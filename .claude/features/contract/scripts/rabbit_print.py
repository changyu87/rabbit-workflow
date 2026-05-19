"""rabbit_print.py — shared renderer for the [rabbit] print convention.

Loads the message registry from
.claude/features/contract/schemas/rabbit-print-messages.json on first use
and caches it for the lifetime of the process. Producers (rabbit-cage hooks,
tdd-subagent scripts) import this module and call the named wrapper API
to compose ANSI-colored output strings. The module itself does not write to
stdout or stderr — it returns strings only.

Public API:
    Low-level:
        rabbit_print(message_id, **kwargs) -> str
        rabbit_subline(text, color="green") -> str
    Block assembler (sole owner of the leading newline):
        rabbit_block(*lines) -> str
    Named wrappers (one per message-id; producers MUST use these):
        r1_branch(branch) -> str
        welcome() -> str
        policy_drift() -> str
        surface_drift(files) -> str
        scope_guard_off() -> str
        scope_guard_bypassed() -> str
        human_approval_bypass() -> str
        skills_updated(names) -> str
        policy_refreshed() -> str
        tdd_transition(from_state, to_state) -> str   (state names upcased)
        tdd_forced(from_state, to_state) -> str       (state names upcased)

Version: 1.1.0
Owner: rabbit-workflow team
Deprecation criterion: when the [rabbit] print convention is replaced by a
    structured logging facility
"""

import json
from pathlib import Path

__all__ = [
    "rabbit_print", "rabbit_subline", "rabbit_block",
    "r1_branch", "welcome", "policy_drift", "surface_drift",
    "scope_guard_off", "scope_guard_bypassed", "human_approval_bypass",
    "skills_updated", "policy_refreshed", "tdd_transition", "tdd_forced",
]

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


def rabbit_block(*lines):
    """Assemble lines into a single string with a leading newline.

    Returns '\\n' + '\\n'.join(lines). The leading newline is the contract
    that Claude Code renders the [rabbit] output on its own row (not inline
    with Stop says: / SessionStart says: chrome). This is the SINGLE
    authoritative place the leading newline lives.
    """
    return "\n" + "\n".join(lines)


def r1_branch(branch):
    return rabbit_print("r1-branch", branch=branch)


def welcome():
    return rabbit_print("welcome")


def policy_drift():
    return rabbit_print("policy-drift")


def surface_drift(files):
    return rabbit_print("surface-drift", files=files)


def scope_guard_off():
    return rabbit_print("scope-guard-off")


def scope_guard_bypassed():
    return rabbit_print("scope-guard-bypassed")


def human_approval_bypass():
    return rabbit_print("human-approval-bypass")


def skills_updated(names):
    return rabbit_print("skills-updated", names=names)


def policy_refreshed():
    return rabbit_print("policy-refreshed")


def tdd_transition(from_state, to_state):
    return rabbit_print(
        "tdd-transition",
        from_state=from_state.upper(),
        to_state=to_state.upper(),
    )


def tdd_forced(from_state, to_state):
    return rabbit_print(
        "tdd-forced",
        from_state=from_state.upper(),
        to_state=to_state.upper(),
    )
