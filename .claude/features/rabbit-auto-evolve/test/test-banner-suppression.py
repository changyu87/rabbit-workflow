#!/usr/bin/env python3
"""test-banner-suppression.py — Inv 14 end-to-end banner suppression contract.

When .rabbit-auto-evolve-active is present at the repo root, the SessionStart
and Stop dispatchers MUST emit the auto-evolve composite banner INSTEAD of
the per-configurable alerts for `human-approval` and `bypass-permissions`.
When the marker is absent, the per-configurable alerts emit normally and
the auto-evolve banner is a no-op.

Test approach: build a synthetic .claude/features/ tree under a tempdir
containing a minimal rabbit-cage feature.json (declaring just the two
suppressed configurables) and a minimal rabbit-auto-evolve feature.json
(no configurables — only the runtime block). Then call the real
contract.lib.runtime APIs in-process across four scenarios:

  S1: marker absent — alerts emit (2 entries), banner returns [].
  S2: marker + adjunct configurables active — alerts filter the two
      suppressed ids (returns 0 entries here), banner returns 2 lines
      with default start hint as line 2.
  S3: marker + .rabbit-auto-evolve-restart-needed — banner line 2 is
      the restart-resume hint substring.
  S4: marker + .rabbit-auto-evolve-aborted (highest precedence) — banner
      line 2 contains 'loop aborted on safety violation' substring.

Imports contract.lib.runtime directly via sys.path injection (same pattern
as contract/test/test-runtime-emit-auto-evolve-banner.py). No shell-outs.
"""

import json
import os
import sys
import tempfile

REPO_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CONTRACT_DIR = os.path.join(REPO_ROOT, ".claude", "features", "contract")
sys.path.insert(0, CONTRACT_DIR)

from lib.runtime import (  # noqa: E402
    emit_auto_evolve_banner,
    emit_auto_evolve_stop_line,
    iterate_configurables_alerts,
)

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def touch(root, name, content=""):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


# Minimal rabbit-cage feature.json declaring just the two configurables
# whose alerts get suppressed when .rabbit-auto-evolve-active is present.
# Storage shapes match the real rabbit-cage entries so _resolve_current_value
# reports `alert-on` when the markers below are set.
RABBIT_CAGE_FJ = {
    "name": "rabbit-cage",
    "configuration": [
        {
            "id": "human-approval",
            "subcommand": "human-approval",
            "storage": {
                "type": "marker-file",
                "path": ".rabbit-human-approval-bypass",
            },
            "values": {
                "true": {"api": "delete_marker", "args": {
                    "path": ".rabbit-human-approval-bypass"}},
                "false": {"api": "write_marker", "args": {
                    "path": ".rabbit-human-approval-bypass",
                    "content": "session"}},
            },
            "default": "true",
            "alert-on": "false",
            "alert-message": {
                "text": "HUMAN APPROVAL BYPASS ACTIVE",
                "icon": "K",
                "color": "red",
            },
        },
        {
            "id": "bypass-permissions",
            "subcommand": "bypass-permissions",
            "storage": {
                "type": "json-key",
                "file": ".claude/settings.local.json",
                "key": "permissions.defaultMode",
            },
            "values": {
                "true": {"api": "set_json_key", "args": {
                    "file": ".claude/settings.local.json",
                    "key": "permissions.defaultMode",
                    "value": "bypassPermissions"}},
                "false": {"api": "delete_json_key", "args": {
                    "file": ".claude/settings.local.json",
                    "key": "permissions.defaultMode"}},
            },
            "default": "false",
            "alert-on": "true",
            "alert-message": {
                "text": "BYPASS-PERMISSIONS MODE ACTIVE",
                "icon": "!",
                "color": "red",
            },
        },
    ],
}

# Minimal rabbit-auto-evolve feature.json — only the runtime block, no
# configurables (the suppression filter targets rabbit-cage configurables,
# not the rabbit-auto-evolve configurable's own alert).
RABBIT_AUTO_EVOLVE_FJ = {
    "name": "rabbit-auto-evolve",
    "runtime": {
        "SessionStart": [{"api": "emit_auto_evolve_banner", "args": {}}],
        "Stop": [{"api": "emit_auto_evolve_stop_line", "args": {}}],
    },
}


def build_repo(td):
    """Lay down the minimal .claude/features/ tree inside tempdir td."""
    cage_dir = os.path.join(td, ".claude", "features", "rabbit-cage")
    ae_dir = os.path.join(td, ".claude", "features", "rabbit-auto-evolve")
    os.makedirs(cage_dir, exist_ok=True)
    os.makedirs(ae_dir, exist_ok=True)
    with open(os.path.join(cage_dir, "feature.json"), "w") as f:
        json.dump(RABBIT_CAGE_FJ, f)
    with open(os.path.join(ae_dir, "feature.json"), "w") as f:
        json.dump(RABBIT_AUTO_EVOLVE_FJ, f)


def set_adjuncts(td):
    """Set BOTH per-configurable adjunct markers so the alerts would fire
    if not suppressed: write .rabbit-human-approval-bypass (marker-file
    semantics: present => 'false' which matches alert-on='false') AND set
    permissions.defaultMode='bypassPermissions' in .claude/settings.local.json
    (matches alert-on='true' after reverse-map).
    """
    touch(td, ".rabbit-human-approval-bypass", "session")
    settings = {"permissions": {"defaultMode": "bypassPermissions"}}
    settings_path = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f)


def filter_target_ids(alerts):
    """Reduce iterate_configurables_alerts output to a count of alerts whose
    text matches one of the two suppressed configurables. We can't read the
    id from the print_result dict (it's just text/icon/color), so we match
    by text substring."""
    suppressed_texts = ("HUMAN APPROVAL BYPASS", "BYPASS-PERMISSIONS MODE")
    return [a for a in alerts
            if any(s in a.get("text", "") for s in suppressed_texts)]


# S1: marker absent — alerts emit normally, banner is a no-op
with tempfile.TemporaryDirectory() as td:
    build_repo(td)
    set_adjuncts(td)
    alerts = iterate_configurables_alerts(repo_root=td)
    targeted = filter_target_ids(alerts)
    banner = emit_auto_evolve_banner(repo_root=td)
    stop = emit_auto_evolve_stop_line(repo_root=td)
    if len(targeted) != 2:
        fail(f"S1: expected 2 per-configurable alerts (human-approval + "
             f"bypass-permissions), got {len(targeted)}: {targeted!r}")
    elif banner != []:
        fail(f"S1: expected banner == [] when marker absent, got {banner!r}")
    elif stop != []:
        fail(f"S1: expected stop == [] when marker absent, got {stop!r}")
    else:
        ok("S1: marker absent -> per-configurable alerts emit, banner is no-op")

# S2: marker present + adjuncts active — alerts for the two ids filtered,
# banner emits 2 lines with default start hint
with tempfile.TemporaryDirectory() as td:
    build_repo(td)
    set_adjuncts(td)
    touch(td, ".rabbit-auto-evolve-active")
    alerts = iterate_configurables_alerts(repo_root=td)
    targeted = filter_target_ids(alerts)
    banner = emit_auto_evolve_banner(repo_root=td)
    if len(targeted) != 0:
        fail(f"S2: expected 0 per-configurable alerts for the two suppressed "
             f"ids, got {len(targeted)}: {targeted!r}")
    elif len(banner) != 2:
        fail(f"S2: expected banner with 2 entries, got {len(banner)}: {banner!r}")
    elif "AUTONOMOUS-EVOLVE MODE ACTIVE" not in banner[0].get("text", ""):
        fail(f"S2: banner line 1 missing AUTONOMOUS-EVOLVE MODE ACTIVE; "
             f"got {banner[0]!r}")
    elif "/rabbit-auto-evolve start" not in banner[1].get("text", ""):
        fail(f"S2: banner line 2 missing '/rabbit-auto-evolve start' default "
             f"start hint; got {banner[1]!r}")
    else:
        ok("S2: marker present -> 2 alerts suppressed, banner emits composite")

# S3: marker + restart-needed -> line 2 is the restart-resume substring
with tempfile.TemporaryDirectory() as td:
    build_repo(td)
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-restart-needed")
    banner = emit_auto_evolve_banner(repo_root=td)
    if len(banner) != 2:
        fail(f"S3: expected 2 entries, got {banner!r}")
    elif "resume after restart: paste /rabbit-auto-evolve start" not in \
            banner[1].get("text", ""):
        fail(f"S3: banner line 2 missing restart-resume substring; "
             f"got {banner[1]!r}")
    else:
        ok("S3: marker + restart-needed -> restart-resume line 2")

# S4: marker + aborted (highest precedence) -> line 2 has aborted substring
with tempfile.TemporaryDirectory() as td:
    build_repo(td)
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    touch(td, ".rabbit-auto-evolve-restart-needed")  # aborted must win
    banner = emit_auto_evolve_banner(repo_root=td)
    if len(banner) != 2:
        fail(f"S4: expected 2 entries, got {banner!r}")
    elif "loop aborted on safety violation" not in banner[1].get("text", ""):
        fail(f"S4: banner line 2 missing 'loop aborted on safety violation' "
             f"substring; got {banner[1]!r}")
    else:
        ok("S4: marker + aborted -> aborted line 2 wins precedence")

if FAIL:
    print("test-banner-suppression: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-banner-suppression: all checks passed.")
