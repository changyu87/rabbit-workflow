#!/usr/bin/env python3
"""test-runtime-iterate-configurables-banner.py — exercises
iterate_configurables_banner: per active configurable, emits EXACTLY ONE
print_result (the alert-message). No auto-generated revoke line is
appended; the configurable's alert-message.text is the SOLE source of
user-facing alert prose (Inv 39).
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import iterate_configurables_banner  # noqa: E402

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


HA = {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "default": "true",
    "alert-on": "false",
    "alert-message": {"text": "HUMAN APPROVAL BYPASS ACTIVE",
                       "icon": "key", "color": "red"},
}

# t1: no overrides active -> empty list
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    r = iterate_configurables_banner(repo_root=td)
    if r == []:
        ok("t1: no active overrides returns empty list")
    else:
        fail(f"t1: expected [], got {r!r}")

# t2: one active override -> exactly one print (alert line only)
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if len(r) != 1:
        fail(f"t2: expected one print (alert only), got {r!r}")
    elif r[0]["type"] != "print":
        fail(f"t2: entry must be type=print, got {r!r}")
    elif r[0]["text"] != "HUMAN APPROVAL BYPASS ACTIVE":
        fail(f"t2: alert line text wrong: {r[0]['text']!r}")
    else:
        ok("t2: active override emits exactly one print — alert only")

# t3: icon/color come from alert-message
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if r[0]["icon"] != "key" or r[0]["color"] != "red":
        fail(f"t3: alert icon/color wrong: {r[0]!r}")
    else:
        ok("t3: alert icon/color come from alert-message")

# Inv 54 — per-id suppression hook driven by .rabbit-auto-evolve-active marker.
# Suppression is scoped to ids {human-approval, bypass-permissions} only; other
# configurables continue to emit even when the marker is present.

BP_BANNER = {
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

# t5: marker absent + both muted configurables active -> unchanged behavior
#     (regression-safe): both still emit (2 entries total — 1 per id).
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA, BP_BANNER])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = iterate_configurables_banner(repo_root=td)
    alert_texts = sorted(x["text"] for x in r)
    if (len(r) == 2
            and alert_texts == ["BYPASS-PERMISSIONS MODE ACTIVE",
                                 "HUMAN APPROVAL BYPASS ACTIVE"]):
        ok("t5: marker absent -> both muted ids emit one alert each (2 entries)")
    else:
        fail(f"t5: expected 2 entries with both alerts, got {r!r}")

# t6: marker present + both muted configurables active -> both suppressed.
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA, BP_BANNER])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    sf = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    with open(os.path.join(td, ".rabbit-auto-evolve-active"), "w") as f:
        f.write("")
    r = iterate_configurables_banner(repo_root=td)
    if r == []:
        ok("t6: marker present + both muted ids active -> suppressed (0 entries)")
    else:
        fail(f"t6: expected zero banner entries, got {r!r}")

# t7: marker present + third unrelated configurable (id=other-thing) alerting
#     -> still emits one entry for that third id (per-id scoping, not blanket).
with tempfile.TemporaryDirectory() as td:
    other = {
        "id": "other-thing",
        "subcommand": "other-thing",
        "storage": {"type": "marker-file", "path": ".other-marker"},
        "default": "true",
        "alert-on": "false",
        "alert-message": {"text": "OTHER THING ACTIVE",
                           "icon": "info", "color": "yellow"},
    }
    make_feature(td, "rabbit-cage", [HA, BP_BANNER, other])
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
    r = iterate_configurables_banner(repo_root=td)
    if (len(r) == 1
            and r[0]["text"] == "OTHER THING ACTIVE"):
        ok("t7: marker present -> per-id scope keeps OTHER THING banner (one entry)")
    else:
        fail(f"t7: expected only OTHER THING alert (one entry), got {r!r}")

if FAIL:
    print("test-runtime-iterate-configurables-banner: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-iterate-configurables-banner: all checks passed.")
