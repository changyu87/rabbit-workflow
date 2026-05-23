#!/usr/bin/env python3
"""test-runtime-iterate-configurables-banner.py — exercises
iterate_configurables_banner: like iterate_configurables_alerts but the
print_result.text is multi-line and includes a canonical revoke command.
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

# t2: one active override -> one print with multi-line text + revoke hint
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if len(r) != 1 or r[0]["type"] != "print":
        fail(f"t2: expected one print, got {r!r}")
    else:
        expected_revoke = "revoke with: /rabbit-config human-approval true"
        if (r[0]["text"].startswith("HUMAN APPROVAL BYPASS ACTIVE")
                and expected_revoke in r[0]["text"]):
            ok("t2: active override emits print with header line + revoke hint")
        else:
            fail(f"t2: text content unexpected: {r[0]['text']!r}")

# t3: icon and color come from alert-message
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "rabbit-cage", [HA])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    if r[0]["icon"] == "key" and r[0]["color"] == "red":
        ok("t3: icon/color taken from alert-message")
    else:
        fail(f"t3: icon/color wrong: {r[0]!r}")

# t4: configurable without default -> revoke target is <unknown>
with tempfile.TemporaryDirectory() as td:
    no_default = dict(HA)
    no_default.pop("default")
    make_feature(td, "rabbit-cage", [no_default])
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = iterate_configurables_banner(repo_root=td)
    # marker present resolves to "false" regardless of default, matches alert-on
    if r and "<unknown>" in r[0]["text"]:
        ok("t4: missing default falls back to <unknown> in revoke hint")
    else:
        fail(f"t4: unexpected: {r!r}")

if FAIL:
    print("test-runtime-iterate-configurables-banner: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-iterate-configurables-banner: all checks passed.")
