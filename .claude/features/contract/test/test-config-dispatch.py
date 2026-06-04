#!/usr/bin/env python3
"""test-config-dispatch.py — exercises contract.lib.config_dispatch.dispatch_config,
the reusable CORE of /rabbit-config's interpreter (phase 3 of #733).

The helper validates the user value, resolves the {api, args} call from the
configuration[] entry's values/actions, applies the mutation by DELEGATING to
contract.lib.mutation (never re-implementing it), emits the branded restart
prompt when restart_required and state changed, and returns a machine-first
structured dict. It never prints and never sys.exit.

Covers (Inv 61):
  - values-style marker round-trip (validate -> write_marker -> restart prompt)
  - json-key-style round-trip (set_json_key)
  - invalid value rejected (no mutation, ok=false)
  - validation rejection (reject_chars / reject_prefix)
  - restart-prompt suppressed on no-op (idempotent re-apply)
  - delegation: the file is written by the mutation primitive, not by the helper
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)
# rabbit_print lives under scripts/ — config_dispatch imports it; ensure the
# path is available for the same reason the production helper makes it available.
sys.path.insert(0, os.path.join(FEATURE_DIR, "scripts"))

from lib.config_dispatch import dispatch_config  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load(root, name):
    with open(os.path.join(root, name)) as f:
        return json.load(f)


# A values-style marker configurable mirroring rabbit-config's scope-guard shape.
MARKER_CFG = {
    "id": "demo-marker",
    "subcommand": "demo-marker",
    "restart_required": True,
    "values": {
        "true": {"api": "write_marker",
                 "args": {"path": ".demo-marker", "content": "on\n"}},
        "false": {"api": "delete_marker",
                  "args": {"path": ".demo-marker"}},
    },
}

# A values-style json-key configurable mirroring rabbit-config's
# bypass-permissions shape (no restart in this fixture).
JSONKEY_CFG = {
    "id": "demo-json",
    "subcommand": "demo-json",
    "values": {
        "fast": {"api": "set_json_key",
                 "args": {"file": ".demo.json", "key": "mode.speed", "value": "fast"}},
        "slow": {"api": "set_json_key",
                 "args": {"file": ".demo.json", "key": "mode.speed", "value": "slow"}},
    },
}

# t1: values-style marker round-trip — validates, writes marker, emits restart
with tempfile.TemporaryDirectory() as root:
    r = dispatch_config(MARKER_CFG, "true", repo_root=root)
    if not r.get("ok"):
        fail(f"t1: dispatch failed: {r}")
    elif not os.path.isfile(os.path.join(root, ".demo-marker")):
        fail("t1: marker file not written by mutation primitive")
    elif open(os.path.join(root, ".demo-marker")).read() != "on\n":
        fail("t1: marker content wrong")
    elif not r.get("restart_prompt"):
        fail(f"t1: restart_required entry should emit restart_prompt: {r}")
    elif "restart Claude" not in r["restart_prompt"]:
        fail(f"t1: restart prompt missing branded text: {r['restart_prompt']!r}")
    elif "demo-marker" not in r["restart_prompt"]:
        fail(f"t1: restart prompt should name the subcommand: {r['restart_prompt']!r}")
    else:
        ok("t1: values-style marker round-trip + restart prompt")

# t2: json-key-style round-trip via set_json_key
with tempfile.TemporaryDirectory() as root:
    r = dispatch_config(JSONKEY_CFG, "fast", repo_root=root)
    if not r.get("ok"):
        fail(f"t2: dispatch failed: {r}")
    elif load(root, ".demo.json") != {"mode": {"speed": "fast"}}:
        fail(f"t2: json key not set: {load(root, '.demo.json')}")
    elif r.get("restart_prompt") is not None:
        fail(f"t2: no restart_required -> restart_prompt should be None: {r}")
    else:
        ok("t2: json-key-style round-trip (set_json_key)")

# t3: invalid value rejected, NO mutation performed
with tempfile.TemporaryDirectory() as root:
    r = dispatch_config(MARKER_CFG, "bogus", repo_root=root)
    if r.get("ok"):
        fail("t3: invalid value should be rejected (ok=false)")
    elif not r.get("error"):
        fail(f"t3: rejection should carry an error message: {r}")
    elif os.path.exists(os.path.join(root, ".demo-marker")):
        fail("t3: rejected value must NOT perform a mutation")
    else:
        ok("t3: invalid value rejected, no mutation")

# t4: validation rejection (reject_chars) — no mutation
with tempfile.TemporaryDirectory() as root:
    cfg = {
        "id": "demo-allow",
        "subcommand": "demo-allow",
        "validation": {"reject_chars": " "},
        "actions": {
            "add": {"api": "append_json_array",
                    "args": {"file": ".demo.json", "key": "list", "value": "{value}"}},
        },
    }
    r = dispatch_config(cfg, "add", repo_root=root, template_value="has space")
    if r.get("ok"):
        fail("t4: value with forbidden char should be rejected")
    elif not r.get("error"):
        fail(f"t4: validation rejection should carry an error: {r}")
    elif os.path.exists(os.path.join(root, ".demo.json")):
        fail("t4: validation-rejected value must NOT perform a mutation")
    else:
        ok("t4: validation (reject_chars) rejection, no mutation")

# t4b: validation rejection (reject_prefix) — no mutation
with tempfile.TemporaryDirectory() as root:
    cfg = {
        "id": "demo-allow2",
        "subcommand": "demo-allow2",
        "validation": {"reject_prefix": "Bash("},
        "actions": {
            "add": {"api": "append_json_array",
                    "args": {"file": ".demo.json", "key": "list", "value": "{value}"}},
        },
    }
    r = dispatch_config(cfg, "add", repo_root=root, template_value="Bash(rm -rf)")
    if r.get("ok"):
        fail("t4b: value with forbidden prefix should be rejected")
    elif not r.get("error"):
        fail(f"t4b: prefix rejection should carry an error: {r}")
    else:
        ok("t4b: validation (reject_prefix) rejection")

# t5: restart prompt suppressed on no-op (idempotent re-apply)
with tempfile.TemporaryDirectory() as root:
    dispatch_config(MARKER_CFG, "true", repo_root=root)
    r = dispatch_config(MARKER_CFG, "true", repo_root=root)  # second time = no-op
    if not r.get("ok"):
        fail(f"t5: idempotent re-apply should still succeed: {r}")
    elif not any("no-op" in m.lower() for m in r.get("messages", [])):
        fail(f"t5: re-apply should report a no-op: {r}")
    elif r.get("restart_prompt") is not None:
        fail(f"t5: no-op must NOT emit a restart prompt: {r['restart_prompt']!r}")
    else:
        ok("t5: restart prompt suppressed on no-op")

# t6: actions-style with templated value substitution
with tempfile.TemporaryDirectory() as root:
    cfg = {
        "id": "demo-tool",
        "subcommand": "demo-tool",
        "actions": {
            "allow": {"api": "append_json_array",
                      "args": {"file": ".s.json", "key": "permissions.allow", "value": "{tool}"}},
        },
    }
    # actions-style: value is the action key; template_value fills the {tool} arg.
    r = dispatch_config(cfg, "allow", repo_root=root, template_value="Read")
    if not r.get("ok"):
        fail(f"t6: templated action dispatch failed: {r}")
    elif load(root, ".s.json") != {"permissions": {"allow": ["Read"]}}:
        fail(f"t6: template not substituted into mutation arg: {load(root, '.s.json')}")
    else:
        ok("t6: actions-style templated value substitution")

# t7: delegation proof — the mutation message comes from contract.lib.mutation,
# not from config_dispatch (the primitive owns the OK: <path> message shape).
with tempfile.TemporaryDirectory() as root:
    r = dispatch_config(JSONKEY_CFG, "slow", repo_root=root)
    if not r.get("ok"):
        fail(f"t7: dispatch failed: {r}")
    elif not any(".demo.json" in m for m in r.get("messages", [])):
        fail(f"t7: mutation-primitive message should flow through: {r['messages']}")
    else:
        ok("t7: delegates to contract.lib.mutation (message flows through)")

# t8: a mutation failure surfaces as ok=false with the primitive's messages
with tempfile.TemporaryDirectory() as root:
    # write a non-array at the json key so append_json_array refuses
    with open(os.path.join(root, ".s.json"), "w") as f:
        json.dump({"permissions": {"allow": "not-an-array"}}, f)
    cfg = {
        "id": "demo-fail",
        "subcommand": "demo-fail",
        "actions": {
            "allow": {"api": "append_json_array",
                      "args": {"file": ".s.json", "key": "permissions.allow", "value": "{tool}"}},
        },
    }
    r = dispatch_config(cfg, "allow", repo_root=root, template_value="Read")
    if r.get("ok"):
        fail("t8: mutation failure should surface ok=false")
    elif not r.get("messages"):
        fail(f"t8: failure should carry the primitive's messages: {r}")
    else:
        ok("t8: mutation failure surfaces ok=false with messages")

if FAIL:
    print("test-config-dispatch: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-config-dispatch: all checks passed.")
