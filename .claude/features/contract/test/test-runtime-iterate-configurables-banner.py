#!/usr/bin/env python3
"""test-runtime-iterate-configurables-banner.py — exercises
iterate_configurables_banner: per active configurable, emits TWO
print_results — the alert-message line and a `revoke with: ...` line.
Both lines are returned as separate print_results so the SessionStart
dispatcher renders each with its own brand prefix and neither is elided
as a continuation line.
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

# t2: one active override -> two prints (alert line + revoke line)
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if len(r) != 2:
        fail(f"t2: expected two prints (alert + revoke), got {r!r}")
    elif r[0]["type"] != "print" or r[1]["type"] != "print":
        fail(f"t2: both entries must be type=print, got {r!r}")
    elif r[0]["text"] != "HUMAN APPROVAL BYPASS ACTIVE":
        fail(f"t2: alert line text wrong: {r[0]['text']!r}")
    elif r[1]["text"] != "revoke with: /rabbit-config human-approval true":
        fail(f"t2: revoke line text wrong: {r[1]['text']!r}")
    else:
        ok("t2: active override emits two prints — alert + revoke")

# t3: icon/color: alert uses alert-message's, revoke shares the color
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if r[0]["icon"] != "key" or r[0]["color"] != "red":
        fail(f"t3: alert icon/color wrong: {r[0]!r}")
    elif r[1]["color"] != "red":
        fail(f"t3: revoke color must match alert color, got {r[1]!r}")
    else:
        ok("t3: alert icon/color from alert-message; revoke color matches alert color")

# t4: configurable without default -> revoke target is <unknown>
with tempfile.TemporaryDirectory() as td:
    no_default = dict(HA)
    no_default.pop("default")
    make_feature(td, "rabbit-cage", [no_default])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if len(r) != 2 or "<unknown>" not in r[1]["text"]:
        fail(f"t4: missing default should produce '<unknown>' in revoke line: {r!r}")
    else:
        ok("t4: missing default falls back to <unknown> in revoke line")

if FAIL:
    print("test-runtime-iterate-configurables-banner: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-iterate-configurables-banner: all checks passed.")
