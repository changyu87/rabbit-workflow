#!/usr/bin/env python3
"""test-runtime-iterate-configurables-alerts.py — exercises
iterate_configurables_alerts: walks every feature's CONFIGURATION array,
evaluates the current value against `alert-on`, returns a list of
print_results for matching configurables.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import iterate_configurables_alerts  # noqa: E402

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

BP_CONF = {
    "id": "bypass-permissions",
    "subcommand": "bypass-permissions",
    "storage": {"type": "json-key",
                 "file": ".claude/settings.local.json",
                 "key": "permissions.defaultMode"},
    "values": {"true": {"api": "set_json_key", "args": {}},
                "false": {"api": "delete_json_key", "args": {}}},
    "default": "false",
    "alert-on": "true",
    "alert-message": {"text": "BYPASS-PERMISSIONS MODE ACTIVE",
                       "icon": "siren", "color": "red"},
}

# Real bypass-permissions configurable with full args (mirrors rabbit-cage feature.json)
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

# t1: no features -> empty list
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".claude", "features"))
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t1: no features returns empty list")
    else:
        fail(f"t1: expected [], got {r!r}")

# t2: marker absent (value "true") with alert-on "false" -> no alert
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF])
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t2: marker absent: value=true, alert-on=false: no alert")
    else:
        fail(f"t2: expected [], got {r!r}")

# t3: marker present (value "false") with alert-on "false" -> one alert
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_alerts(repo_root=td)
    if (len(r) == 1 and r[0]["type"] == "print"
            and r[0]["text"] == "HUMAN APPROVAL BYPASS ACTIVE"
            and r[0]["color"] == "red"):
        ok("t3: marker present: value=false matches alert-on -> print emitted")
    else:
        fail(f"t3: unexpected {r!r}")

# t4: json-key absent -> uses default; default doesn't match alert-on -> no alert
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [BP_CONF])
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t4: json-key absent: default 'false' != alert-on 'true' -> no alert")
    else:
        fail(f"t4: expected [], got {r!r}")

# t5: json-key value literally matches alert-on -> alert
with tempfile.TemporaryDirectory() as td:
    custom = {
        "id": "demo",
        "subcommand": "demo",
        "storage": {"type": "json-key", "file": "cfg.json", "key": "mode"},
        "values": {"on": {"api": "set_json_key", "args": {}},
                    "off": {"api": "delete_json_key", "args": {}}},
        "default": "off",
        "alert-on": "on",
        "alert-message": {"text": "DEMO MODE ACTIVE", "icon": "info", "color": "yellow"},
    }
    make_feature(td, "demo-feat", [custom])
    with open(os.path.join(td, "cfg.json"), "w") as f:
        json.dump({"mode": "on"}, f)
    r = iterate_configurables_alerts(repo_root=td)
    if len(r) == 1 and r[0]["text"] == "DEMO MODE ACTIVE":
        ok("t5: json-key literal match to alert-on emits alert")
    else:
        fail(f"t5: unexpected {r!r}")

# t6: json-key non-matching string, no value in args -> no translation -> no alert
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [BP_CONF])
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = iterate_configurables_alerts(repo_root=td)
    # BP_CONF has empty args for set_json_key, so no reverse-lookup translation
    # is possible; stored "bypassPermissions" stays untranslated and != "true".
    if r == []:
        ok("t6: json-key with no args.value: no translation, no alert")
    else:
        fail(f"t6: expected [], got {r!r}")

# t7: configurable without alert-on is skipped
with tempfile.TemporaryDirectory() as td:
    no_alert = {
        "id": "x", "subcommand": "x",
        "storage": {"type": "marker-file", "path": ".x"},
        "values": {"true": {"api": "delete_marker", "args": {}},
                    "false": {"api": "write_marker", "args": {}}},
        "default": "true",
    }
    make_feature(td, "f", [no_alert])
    with open(os.path.join(td, ".x"), "w") as f:
        f.write("")
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t7: configurable without alert-on skipped")
    else:
        fail(f"t7: expected [], got {r!r}")

# t8: action-style (json-array) configurable is skipped (no values to check)
with tempfile.TemporaryDirectory() as td:
    arr = {
        "id": "tools", "subcommand": "allowed-tools",
        "storage": {"type": "json-array", "file": "x.json", "key": "perms"},
        "actions": {"add": {"api": "append_json_array", "args": {}}},
    }
    make_feature(td, "f", [arr])
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t8: json-array (action-style) configurable skipped")
    else:
        fail(f"t8: expected [], got {r!r}")

# t9: iteration order alphabetical by feature name
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "z-feat", [
        {**HA_CONF, "id": "z-hap", "alert-message":
            {"text": "Z", "icon": "z", "color": "red"}}])
    make_feature(td, "a-feat", [
        {**HA_CONF, "id": "a-hap", "alert-message":
            {"text": "A", "icon": "a", "color": "red"}}])
    # marker shared path, so both fire
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_alerts(repo_root=td)
    texts = [x["text"] for x in r]
    if texts == ["A", "Z"]:
        ok("t9: features iterated alphabetically (A before Z)")
    else:
        fail(f"t9: order unexpected: {texts}")

# t10: json-key bypass-permissions with full args -> stored "bypassPermissions"
#      reverse-maps to user-facing "true" -> matches alert-on "true" -> alert fires
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [BP_CONF_REAL])
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = iterate_configurables_alerts(repo_root=td)
    if (len(r) == 1 and r[0]["type"] == "print"
            and r[0]["text"] == "BYPASS-PERMISSIONS MODE ACTIVE"
            and r[0]["color"] == "red"):
        ok("t10: json-key with args.value: stored 'bypassPermissions' translates to 'true' -> alert")
    else:
        fail(f"t10: expected one BYPASS-PERMISSIONS alert, got {r!r}")

# Inv 64 — per-id suppression hook driven by .rabbit-auto-evolve-active marker.
# Suppression is scoped to ids {human-approval, bypass-permissions} only; other
# configurables continue to emit even when the marker is present.

# t11: marker absent + both muted configurables in alert-on state -> unchanged
#      behavior (regression-safe): both still emit.
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF, BP_CONF_REAL])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = iterate_configurables_alerts(repo_root=td)
    texts = sorted(x["text"] for x in r)
    if texts == ["BYPASS-PERMISSIONS MODE ACTIVE", "HUMAN APPROVAL BYPASS ACTIVE"]:
        ok("t11: marker absent -> both muted ids still emit (regression unchanged)")
    else:
        fail(f"t11: expected both alerts when marker absent, got {texts}")

# t12: marker present + both muted configurables active -> both suppressed.
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA_CONF, BP_CONF_REAL])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    with open(os.path.join(td, ".rabbit-auto-evolve-active"), "w") as f:
        f.write("")
    r = iterate_configurables_alerts(repo_root=td)
    if r == []:
        ok("t12: marker present + both muted ids active -> suppressed (0 entries)")
    else:
        fail(f"t12: expected zero alerts (both ids suppressed), got {r!r}")

# t13: marker present + third unrelated configurable (id=other-thing) alerting
#      -> still emits for that third id (per-id scoping, not blanket).
with tempfile.TemporaryDirectory() as td:
    other = {
        "id": "other-thing",
        "subcommand": "other-thing",
        "storage": {"type": "marker-file", "path": ".other-marker"},
        "values": {"true": {"api": "delete_marker", "args": {}},
                    "false": {"api": "write_marker", "args": {}}},
        "default": "true",
        "alert-on": "false",
        "alert-message": {"text": "OTHER THING ACTIVE",
                           "icon": "info", "color": "yellow"},
    }
    make_feature(td, "rabbit-cage", [HA_CONF, BP_CONF_REAL, other])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    with open(os.path.join(td, ".other-marker"), "w") as f:
        f.write("")
    with open(os.path.join(td, ".rabbit-auto-evolve-active"), "w") as f:
        f.write("")
    r = iterate_configurables_alerts(repo_root=td)
    if (len(r) == 1 and r[0]["text"] == "OTHER THING ACTIVE"):
        ok("t13: marker present -> per-id scope keeps OTHER THING ACTIVE alert")
    else:
        fail(f"t13: expected only OTHER THING ACTIVE alert, got {r!r}")

if FAIL:
    print("test-runtime-iterate-configurables-alerts: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-iterate-configurables-alerts: all checks passed.")
