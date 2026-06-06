#!/usr/bin/env python3
"""test-plugin-scope-override-path-consistent.py — Inv 25.

Source-inspection e2e: the session-override marker `.rabbit-scope-override`
MUST resolve to a SINGLE per-mode canonical location across all five
consumers. In plugin mode that is `<rabbit_root>/.rabbit-scope-override`
(where `<rabbit_root>` is the directory whose `.rabbit/.runtime/mode`
contains the literal string `'plugin'`); in standalone mode that is
`<repo_root>/.rabbit-scope-override`.

The five consumers checked:
  (1) scope-guard.py three-option DENY message text (string mentions
      `.rabbit/.rabbit-scope-override` in plugin mode)
  (2) scope-guard.py allowlist carves out `.rabbit/.rabbit-scope-override`
      in plugin mode (so the user/agent can WRITE the marker)
  (3) scope-guard.py `_consume_override()` reads from the per-mode
      location (uses a helper or branches on mode_file)
  (4) scripts/scope-guard-on.py deletes the per-mode location
  (5) feature.json runtime.Stop AND runtime.SessionStart both declare
      check_marker_alert with path `'.rabbit-scope-override'` — the
      contract.lib.runtime helper resolves that relative path against
      repo_root which equals `<rabbit_root>` in plugin mode.

This test pins the SOURCE-LEVEL invariant. Runtime behaviour is pinned
by the three other tests in this cycle.
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SCOPE_GUARD = REPO / ".claude/features/rabbit-cage/hooks/scope-guard.py"
SCOPE_GUARD_ON = REPO / ".claude/features/rabbit-cage/scripts/scope-guard-on.py"
FEATURE_JSON = REPO / ".claude/features/rabbit-cage/feature.json"

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


print("test-plugin-scope-override-path-consistent.py")
print()

sg_src = SCOPE_GUARD.read_text()
sgon_src = SCOPE_GUARD_ON.read_text()
fj = json.loads(FEATURE_JSON.read_text())

# ---------------------------------------------------------------- t1
print("=== t1: scope-guard.py DENY message names plugin-mode override path ===")
# The plugin-mode default-deny structured message must point the user at
# .rabbit/.rabbit-scope-override (the per-mode canonical location), not
# the bare .rabbit-scope-override (which in plugin mode resolves to the
# user-project root and is silent).
if ".rabbit/.rabbit-scope-override" in sg_src:
    ok("scope-guard.py source mentions plugin-mode path '.rabbit/.rabbit-scope-override'")
else:
    fail_t(
        "scope-guard.py source does not mention '.rabbit/.rabbit-scope-override' — "
        "the three-option DENY message in plugin mode must name the per-mode "
        "canonical location so the user knows where to write the override."
    )

# ---------------------------------------------------------------- t2
print()
print("=== t2: scope-guard.py allowlists .rabbit/.rabbit-scope-override in plugin mode ===")
# The plugin-mode .rabbit/** DENY has carve-outs (.rabbit/CLAUDE.md,
# .rabbit/.gitignore). Add .rabbit/.rabbit-scope-override so the user
# (or agent) can WRITE the marker even when plugin-mode .rabbit/** is
# otherwise locked.
if re.search(
    r"['\"]\.rabbit/\.rabbit-scope-override['\"]",
    sg_src,
):
    ok("scope-guard.py contains '.rabbit/.rabbit-scope-override' carve-out literal")
else:
    fail_t(
        "scope-guard.py does not contain a '.rabbit/.rabbit-scope-override' "
        "carve-out literal — plugin mode would refuse the user's attempt "
        "to write the override marker."
    )

# ---------------------------------------------------------------- t3
print()
print("=== t3: _consume_override() reads from per-mode location ===")
# The _consume_override helper currently resolves the marker via REPO_ROOT
# (the git toplevel, == user-project root in plugin mode). The fix wires
# it to the per-mode location: in plugin mode, the rabbit install root,
# i.e. <REPO_ROOT>/.rabbit/.rabbit-scope-override.
# We accept either of two source shapes:
#   (a) helper function name (e.g. _override_marker_path or
#       _override_path) that contains a plugin/mode branch returning
#       `<rabbit-root>/.rabbit-scope-override`, OR
#   (b) inline branching on mode within _consume_override referring to
#       `.rabbit/.rabbit-scope-override`.
consume_block = re.search(
    r"def _consume_override\b.*?(?=\ndef |\Z)",
    sg_src,
    re.DOTALL,
)
if not consume_block:
    fail_t("could not locate _consume_override() definition in scope-guard.py")
else:
    block = consume_block.group(0)
    # Look for the override path being resolved relative to .rabbit/ in
    # plugin mode. Accept either the literal '.rabbit/.rabbit-scope-override'
    # or a helper-derived path that references '.rabbit'.
    helper_paths = re.findall(r"_(?:override|scope_override)_path\s*\(", sg_src)
    if (
        ".rabbit/.rabbit-scope-override" in block
        or ".rabbit\" / \".rabbit-scope-override" in block
        or "'.rabbit'" in block and ".rabbit-scope-override" in block
        or helper_paths
    ):
        ok("_consume_override() resolves marker via per-mode location helper or inline branch")
    else:
        fail_t(
            "_consume_override() body does not reference the per-mode "
            "plugin-mode location ('.rabbit/.rabbit-scope-override' or a "
            "helper that yields it). Current body: "
            + block[:400]
        )

# ---------------------------------------------------------------- t4
print()
print("=== t4: scope-guard-on.py deletes from per-mode location ===")
# Mirror of t3 for the revoke script.
if ".rabbit/.rabbit-scope-override" in sgon_src or (
    ".rabbit" in sgon_src and ".rabbit-scope-override" in sgon_src
    and re.search(r"mode\s*==\s*['\"]plugin['\"]", sgon_src)
):
    ok("scope-guard-on.py source resolves override marker via per-mode location")
else:
    fail_t(
        "scope-guard-on.py does not contain a per-mode override-path "
        "resolution. Current source must reference plugin-mode "
        "'.rabbit/.rabbit-scope-override' branch."
    )

# ---------------------------------------------------------------- t5
print()
print("=== t5: feature.json declares check_marker_alert in BOTH Stop and SessionStart ===")
stop_entries = fj.get("runtime", {}).get("Stop", [])
ss_entries = fj.get("runtime", {}).get("SessionStart", [])


def _override_alert_entry(entries):
    for e in entries:
        if e.get("api") != "check_marker_alert":
            continue
        args = e.get("args", {})
        if args.get("path") == ".rabbit-scope-override" and args.get("content") == "session":
            return e
    return None


stop_alert = _override_alert_entry(stop_entries)
ss_alert = _override_alert_entry(ss_entries)

if stop_alert is not None:
    ok("runtime.Stop declares check_marker_alert for '.rabbit-scope-override' content='session'")
else:
    fail_t(
        "runtime.Stop missing check_marker_alert entry for "
        "'.rabbit-scope-override' content='session'"
    )

if ss_alert is not None:
    ok("runtime.SessionStart declares check_marker_alert for '.rabbit-scope-override' content='session'")
else:
    fail_t(
        "runtime.SessionStart missing check_marker_alert entry for "
        "'.rabbit-scope-override' content='session' (Inv 16 amendment)"
    )

# Both alert blocks must use the same banner shape — text contains 'SCOPE
# GUARD OFF', icon '🔓', color 'red'.
for label, entry in [("Stop", stop_alert), ("SessionStart", ss_alert)]:
    if entry is None:
        continue
    alert = entry.get("args", {}).get("alert", {})
    if "SCOPE GUARD OFF" in alert.get("text", "") and alert.get("icon") == "🔓" and alert.get("color") == "red":
        ok(f"{label} alert: text contains 'SCOPE GUARD OFF', icon '🔓', color 'red'")
    else:
        fail_t(
            f"{label} alert shape wrong; got "
            f"text={alert.get('text')!r} icon={alert.get('icon')!r} "
            f"color={alert.get('color')!r}"
        )

# ---------------------------------------------------------------- t6
print()
print("=== t6: SessionStart entry count is SIX (Inv 16 + Inv 40c bypass alert + #917 plugin-path alert) ===")
# #780 re-homed the bypass-permissions per-feature alert as a SessionStart
# emit_configurable_alert entry appended after the scope-guard check_marker_alert.
# #917 added a SECOND scope-guard check_marker_alert for the plugin-mode
# canonical marker path '.rabbit/.rabbit-scope-override'.
if len(ss_entries) == 6:
    ok("SessionStart declares exactly 6 entries")
else:
    fail_t(
        f"SessionStart declares {len(ss_entries)} entries; "
        f"expected 6. APIs: {[e.get('api') for e in ss_entries]}"
    )

# emit_configurable_alert (bypass-permissions) is the LAST SessionStart entry,
# appended after the scope-guard check_marker_alert (#780).
if ss_entries and ss_entries[-1].get("api") == "emit_configurable_alert":
    ok("emit_configurable_alert (bypass-permissions) is the LAST SessionStart entry")
else:
    fail_t(
        "emit_configurable_alert is not the last SessionStart entry. "
        f"Order: {[e.get('api') for e in ss_entries]}"
    )
if any(e.get("api") == "check_marker_alert" for e in ss_entries):
    ok("check_marker_alert (scope-guard) remains a SessionStart entry")
else:
    fail_t(
        "check_marker_alert missing from SessionStart. "
        f"Order: {[e.get('api') for e in ss_entries]}"
    )

# ---------------------------------------------------------------- t7
print()
print("=== t7: BOTH Stop and SessionStart declare the PLUGIN-PATH override alert (#917) ===")
# The plugin-mode canonical marker location is '.rabbit/.rabbit-scope-override'
# relative to repo_root (Inv 25). check_marker_alert resolves a relative path
# against repo_root, so the standalone '.rabbit-scope-override' entry alone
# never fires in plugin mode — a second entry with the plugin path is required.


def _plugin_override_alert_entry(entries):
    for e in entries:
        if e.get("api") != "check_marker_alert":
            continue
        args = e.get("args", {})
        if (
            args.get("path") == ".rabbit/.rabbit-scope-override"
            and args.get("content") == "session"
        ):
            return e
    return None


for label, entries in [("Stop", stop_entries), ("SessionStart", ss_entries)]:
    entry = _plugin_override_alert_entry(entries)
    if entry is None:
        fail_t(
            f"runtime.{label} missing check_marker_alert for plugin path "
            "'.rabbit/.rabbit-scope-override' content='session' (#917)"
        )
        continue
    alert = entry.get("args", {}).get("alert", {})
    if (
        "SCOPE GUARD OFF" in alert.get("text", "")
        and alert.get("icon") == "🔓"
        and alert.get("color") == "red"
    ):
        ok(
            f"{label} plugin-path alert present with text 'SCOPE GUARD OFF', "
            "icon '🔓', color 'red'"
        )
    else:
        fail_t(
            f"{label} plugin-path alert shape wrong; got "
            f"text={alert.get('text')!r} icon={alert.get('icon')!r} "
            f"color={alert.get('color')!r}"
        )

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
