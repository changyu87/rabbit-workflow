#!/usr/bin/env python3
"""test-runtime-emit-configurable-alert.py — exercises
emit_configurable_alert: on-demand sibling of iterate_configurables_alerts.
Resolves a single configurable by feature_name + configurable_id, evaluates
its current value against alert-on, returns print_result on match,
ok_result on miss, or error_result on resolution failure.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import emit_configurable_alert  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_feature(root, name, configuration):
    fdir = os.path.join(root, ".claude", "features", name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": name, "version": "1.0.0", "owner": "x",
                   "configuration": configuration}, f)


HA_CONF = {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "values": {"true": {"api": "delete_marker", "args": {}},
                "false": {"api": "write_marker", "args": {}}},
    "default": "true",
    "alert-on": "false",
    "alert-message": {"text": "HUMAN APPROVAL BYPASS ACTIVE",
                       "icon": "key", "color": "red"},
}

BP_CONF_REAL = {
    "id": "bypass-permissions",
    "subcommand": "bypass-permissions",
    "storage": {"type": "json-key",
                 "file": ".claude/settings.local.json",
                 "key": "permissions.defaultMode"},
    "values": {
        "true":  {"api": "set_json_key",    "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode", "value": "bypassPermissions"}},
        "false": {"api": "delete_json_key", "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode"}},
    },
    "default": "false",
    "alert-on": "true",
    "alert-message": {"text": "BYPASS-PERMISSIONS MODE ACTIVE",
                       "icon": "siren", "color": "red"},
}


# t1: marker-file configurable with alert-on=false and marker absent -> ok_result
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF])
    r = emit_configurable_alert("rabbit-cage", "human-approval", repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: marker absent (value=true) != alert-on=false -> ok_result")
    else:
        fail(f"t1: expected ok_result, got {r!r}")

# t2: marker-file configurable with marker present -> print_result
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = emit_configurable_alert("rabbit-cage", "human-approval", repo_root=td)
    if (r.get("type") == "print"
            and r.get("text") == "HUMAN APPROVAL BYPASS ACTIVE"
            and r.get("icon") == "key"
            and r.get("color") == "red"):
        ok("t2: marker present matches alert-on -> print_result with exact text/icon/color")
    else:
        fail(f"t2: unexpected {r!r}")

# t3: unknown feature_name -> error_result
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".claude", "features"))
    r = emit_configurable_alert("nonexistent-feature", "human-approval", repo_root=td)
    if r.get("type") == "error" and isinstance(r.get("message"), str):
        ok("t3: unknown feature_name -> error_result")
    else:
        fail(f"t3: expected error_result, got {r!r}")

# t4: unknown configurable_id on existing feature -> error_result
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF])
    r = emit_configurable_alert("rabbit-cage", "no-such-id", repo_root=td)
    if r.get("type") == "error" and isinstance(r.get("message"), str):
        ok("t4: unknown configurable_id -> error_result")
    else:
        fail(f"t4: expected error_result, got {r!r}")

# t5: configurable missing alert-message -> error_result
with tempfile.TemporaryDirectory() as td:
    no_msg = {
        "id": "no-msg",
        "subcommand": "no-msg",
        "storage": {"type": "marker-file", "path": ".x"},
        "values": {"true": {"api": "delete_marker", "args": {}},
                    "false": {"api": "write_marker", "args": {}}},
        "default": "true",
        "alert-on": "false",
    }
    make_feature(td, "feat-no-msg", [no_msg])
    r = emit_configurable_alert("feat-no-msg", "no-msg", repo_root=td)
    if r.get("type") == "error" and isinstance(r.get("message"), str):
        ok("t5: configurable missing alert-message -> error_result")
    else:
        fail(f"t5: expected error_result, got {r!r}")

# t6: json-key bypass-permissions with full args -> stored "bypassPermissions"
#     reverse-maps to "true" matching alert-on="true" -> print_result
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [BP_CONF_REAL])
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = emit_configurable_alert("rabbit-cage", "bypass-permissions", repo_root=td)
    if (r.get("type") == "print"
            and r.get("text") == "BYPASS-PERMISSIONS MODE ACTIVE"
            and r.get("icon") == "siren"
            and r.get("color") == "red"):
        ok("t6: json-key reverse-maps to 'true' matching alert-on -> print_result")
    else:
        fail(f"t6: unexpected {r!r}")

# t7: action-style (json-array) configurable -> ok_result
with tempfile.TemporaryDirectory() as td:
    arr = {
        "id": "tools", "subcommand": "allowed-tools",
        "storage": {"type": "json-array", "file": "x.json", "key": "perms"},
        "actions": {"add": {"api": "append_json_array", "args": {}}},
        "alert-on": "true",
        "alert-message": {"text": "X", "icon": "x", "color": "red"},
    }
    make_feature(td, "feat-arr", [arr])
    r = emit_configurable_alert("feat-arr", "tools", repo_root=td)
    if r == {"type": "ok"}:
        ok("t7: action-style json-array configurable -> ok_result")
    else:
        fail(f"t7: expected ok_result, got {r!r}")

if FAIL:
    print("test-runtime-emit-configurable-alert: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-configurable-alert: all checks passed.")
