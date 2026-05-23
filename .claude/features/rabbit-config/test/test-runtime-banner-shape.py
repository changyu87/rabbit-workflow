#!/usr/bin/env python3
"""test-runtime-banner-shape.py — Inv 16-17 (BUG-3 regression).

End-to-end test for iterate_configurables_banner emission shape via the
deployed session-start-dispatcher.

  t16a: marker-file override (human-approval) emits both alert and revoke
        lines, each on its own brand-prefixed line in systemMessage
  t16b: json-key override (bypass-permissions) emits both alert and revoke
        lines, each on its own brand-prefixed line in systemMessage
  t16c: every alert line and every revoke line begins with the brand
        prefix (no multi-line continuation that would be elided by the
        SessionStart TUI)
  t17a: with no overrides active, the banner alerts are absent from
        systemMessage (welcome banner still present)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

CONTRACT_SRC = os.path.join(REPO_ROOT, ".claude/features/contract")
RABBIT_CAGE_SRC = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
RABBIT_CONFIG_SRC = os.path.join(REPO_ROOT, ".claude/features/rabbit-config")
POLICY_SRC = os.path.join(REPO_ROOT, ".claude/features/policy")
DISPATCHER = os.path.join(RABBIT_CAGE_SRC, "hooks/session-start-dispatcher.py")

BRAND = "[🐇 rabbit 🐇]"

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


def make_repo(tmp):
    """Clone contract, rabbit-cage, and policy into a fake repo so the
    dispatcher can find feature.json files and the runtime/print modules.
    """
    features_root = os.path.join(tmp, ".claude", "features")
    os.makedirs(features_root, exist_ok=True)
    shutil.copytree(CONTRACT_SRC, os.path.join(features_root, "contract"))
    shutil.copytree(RABBIT_CAGE_SRC, os.path.join(features_root, "rabbit-cage"))
    shutil.copytree(RABBIT_CONFIG_SRC, os.path.join(features_root, "rabbit-config"))
    shutil.copytree(POLICY_SRC, os.path.join(features_root, "policy"))


def run_dispatcher(tmp):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = tmp
    return subprocess.run(
        [sys.executable, DISPATCHER],
        cwd=tmp, capture_output=True, text=True, env=env, input=""
    )


def strip_ansi(s):
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


# t16a: marker-file override emits alert + revoke as separate brand-prefixed lines
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    # Activate human-approval bypass (marker-file storage)
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = run_dispatcher(td)
    if r.returncode != 0:
        fail("16a", f"dispatcher exit {r.returncode}. stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            fail("16a", f"dispatcher stdout not JSON: {e}. stdout={r.stdout!r}")
            payload = {}
        msg = strip_ansi(payload.get("systemMessage", ""))
        lines = [ln for ln in msg.split("\n") if ln.strip()]
        alert_lines = [ln for ln in lines if "HUMAN APPROVAL BYPASS" in ln]
        revoke_lines = [ln for ln in lines if "rabbit-config human-approval" in ln]
        if not alert_lines:
            fail("16a", f"no alert line found. systemMessage={msg!r}")
        elif not all(ln.lstrip().startswith(BRAND) for ln in alert_lines):
            fail("16a", f"alert line not brand-prefixed: {alert_lines!r}")
        elif not revoke_lines:
            fail("16a", f"no revoke line found. systemMessage={msg!r}")
        elif not all(ln.lstrip().startswith(BRAND) for ln in revoke_lines):
            fail("16a", f"revoke line not brand-prefixed: {revoke_lines!r}")
        else:
            ok("16a", "marker-file alert + revoke each on own brand-prefixed line")

# t16b: json-key override emits alert + revoke as separate brand-prefixed lines
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    settings = os.path.join(td, ".claude", "settings.local.json")
    with open(settings, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = run_dispatcher(td)
    if r.returncode != 0:
        fail("16b", f"dispatcher exit {r.returncode}. stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            fail("16b", f"dispatcher stdout not JSON: {e}. stdout={r.stdout!r}")
            payload = {}
        msg = strip_ansi(payload.get("systemMessage", ""))
        lines = [ln for ln in msg.split("\n") if ln.strip()]
        alert_lines = [ln for ln in lines if "BYPASS-PERMISSIONS MODE ACTIVE" in ln]
        revoke_lines = [ln for ln in lines if "rabbit-config bypass-permissions" in ln]
        if not alert_lines:
            fail("16b", f"no alert line found. systemMessage={msg!r}")
        elif not all(ln.lstrip().startswith(BRAND) for ln in alert_lines):
            fail("16b", f"alert line not brand-prefixed: {alert_lines!r}")
        elif not revoke_lines:
            fail("16b", f"no revoke line found. systemMessage={msg!r}")
        elif not all(ln.lstrip().startswith(BRAND) for ln in revoke_lines):
            fail("16b", f"revoke line not brand-prefixed: {revoke_lines!r}")
        else:
            ok("16b", "json-key alert + revoke each on own brand-prefixed line")

# t16c: both overrides active — every non-blank line is brand-prefixed
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    settings = os.path.join(td, ".claude", "settings.local.json")
    with open(settings, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = run_dispatcher(td)
    if r.returncode != 0:
        fail("16c", f"dispatcher exit {r.returncode}. stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            fail("16c", f"dispatcher stdout not JSON: {e}. stdout={r.stdout!r}")
            payload = {}
        msg = strip_ansi(payload.get("systemMessage", ""))
        non_blank = [ln for ln in msg.split("\n") if ln.strip()]
        non_brand = [ln for ln in non_blank if not ln.lstrip().startswith(BRAND)]
        if non_brand:
            fail("16c", f"non-brand-prefixed lines present (TUI elision risk): {non_brand!r}")
        else:
            ok("16c", f"all {len(non_blank)} non-blank lines are brand-prefixed")

# t17a: no overrides active — alert lines absent, welcome still present
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    r = run_dispatcher(td)
    if r.returncode != 0:
        fail("17a", f"dispatcher exit {r.returncode}. stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            fail("17a", f"dispatcher stdout not JSON: {e}. stdout={r.stdout!r}")
            payload = {}
        msg = strip_ansi(payload.get("systemMessage", ""))
        if "HUMAN APPROVAL BYPASS" in msg or "BYPASS-PERMISSIONS MODE ACTIVE" in msg:
            fail("17a", f"alert text appears when no overrides are active: {msg!r}")
        elif "Welcome" not in msg:
            fail("17a", f"welcome banner missing: {msg!r}")
        else:
            ok("17a", "no-override case: welcome present, no alert lines")

if FAIL:
    print("test-runtime-banner-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-banner-shape: all checks passed.")
