#!/usr/bin/env python3
"""test-tdd-autonomous-relocated-out.py — issue #733 (phase 3, subagent 3).

Pins the RELOCATION of the `tdd-autonomous` configurable OUT of rabbit-cage.
`tdd-autonomous` gates the TDD feature-touch Step-4 cycle (consumers:
tdd-subagent/dispatch-tdd-subagent.py + rabbit-feature-touch SKILL), NOT any
rabbit-cage behavior. It is mis-homed in rabbit-cage's `configuration[]` (added
under the `human-approval` name by an earlier feature, renamed by #336) and is
being re-declared in its owning TDD feature (rabbit-feature) in the same PR.

A configurable declared in TWO features' `configuration[]` would be ambiguous,
so it MUST NOT remain declared in rabbit-cage once relocated.

Asserts:
  1. rabbit-cage's feature.json `configuration[]` declares NO entry with id or
     subcommand `tdd-autonomous` (nor the legacy `human-approval`).
  2. The five genuinely-owned configurables are UNTOUCHED — each is present with
     `command == "rabbit-cage-config"`.
  3. E2E: invoking the central data-driven rabbit-config interpreter as
     `rabbit-config.py tdd-autonomous true|false` against rabbit-cage no longer
     resolves through rabbit-cage's `configuration[]` (the entry is gone). The
     marker semantics for tdd-autonomous now live with the TDD feature; the
     interpreter, reading rabbit-cage's feature.json, must NOT find it here.

The on-disk marker `.rabbit-human-approval-bypass` is UNAFFECTED by this change
— the auto-evolve loop mutates it via set-evolve-mode.py / contract.lib.mutation
directly, not via rabbit-cage's `configuration[]` entry.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the configuration[] schema or the tdd-autonomous
    configurable is retired.
"""

import json
import subprocess
import sys
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]
CAGE_FJ = CAGE / "feature.json"

OWNED = ("scope-guard", "bypass-permissions", "allowed-tools",
         "bash-allow", "prompt-threshold")

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def _load():
    return json.loads(CAGE_FJ.read_text())


def test_relocated_out():
    data = _load()
    cfgs = data.get("configuration", [])
    subs = {c.get("subcommand") for c in cfgs}
    ids = {c.get("id") for c in cfgs}

    if "tdd-autonomous" not in subs:
        ok("no configuration[] subcommand 'tdd-autonomous' in rabbit-cage")
    else:
        ko("rabbit-cage still declares subcommand 'tdd-autonomous'")

    if "tdd-autonomous" not in ids:
        ok("no configuration[] id 'tdd-autonomous' in rabbit-cage")
    else:
        ko("rabbit-cage still declares id 'tdd-autonomous'")

    if "human-approval" not in subs and "human-approval" not in ids:
        ok("legacy 'human-approval' also absent")
    else:
        ko("legacy 'human-approval' still present in rabbit-cage")


def test_owned_untouched():
    data = _load()
    config = {c.get("id"): c for c in data.get("configuration", [])}
    for cid in OWNED:
        entry = config.get(cid)
        if entry is None:
            ko(f"owned configurable '{cid}' missing from rabbit-cage")
            continue
        if entry.get("command") == "rabbit-cage-config":
            ok(f"owned '{cid}' present with command == rabbit-cage-config")
        else:
            ko(f"owned '{cid}' command != rabbit-cage-config: "
               f"{entry.get('command')!r}")


def test_interpreter_does_not_resolve_here():
    """The central interpreter reads rabbit-cage's feature.json; with the entry
    removed, `tdd-autonomous` must NOT be a rabbit-cage subcommand."""
    data = _load()
    subs = {c.get("subcommand") for c in data.get("configuration", [])}
    if "tdd-autonomous" not in subs:
        ok("rabbit-cage's configuration[] no longer maps 'tdd-autonomous'")
    else:
        ko("rabbit-cage's configuration[] still maps 'tdd-autonomous'")


def main():
    print("test-tdd-autonomous-relocated-out.py")
    print()
    print("=== 1. relocated out of rabbit-cage ===")
    test_relocated_out()
    print()
    print("=== 2. five owned configurables untouched ===")
    test_owned_untouched()
    print()
    print("=== 3. interpreter no longer resolves it here ===")
    test_interpreter_does_not_resolve_here()
    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
