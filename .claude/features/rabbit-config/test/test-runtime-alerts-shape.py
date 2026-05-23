#!/usr/bin/env python3
"""test-runtime-alerts-shape.py — Inv 18 (BUG-2 regression).

End-to-end test for iterate_configurables_alerts emission shape via the
deployed stop-dispatcher. Covers both storage types (marker-file and
json-key) to close the Plan D verification gap that allowed BUG-2.

  t18a: marker-file override (human-approval) emits exactly one
        brand-prefixed alert line in systemMessage
  t18b: json-key override (bypass-permissions, alert-on='true' maps via
        reverse-lookup to stored 'bypassPermissions') emits exactly one
        brand-prefixed alert line
  t18c: with no overrides active, no alert lines appear
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
DISPATCHER = os.path.join(RABBIT_CAGE_SRC, "hooks/stop-dispatcher.py")

BRAND = "[🐇 rabbit 🐇]"

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


def make_repo(tmp):
    features_root = os.path.join(tmp, ".claude", "features")
    os.makedirs(features_root, exist_ok=True)
    shutil.copytree(CONTRACT_SRC, os.path.join(features_root, "contract"))
    shutil.copytree(RABBIT_CAGE_SRC, os.path.join(features_root, "rabbit-cage"))
    shutil.copytree(RABBIT_CONFIG_SRC, os.path.join(features_root, "rabbit-config"))
    shutil.copytree(POLICY_SRC, os.path.join(features_root, "policy"))
    # CLAUDE.md and other rabbit-cage runtime artifacts: stop-dispatcher
    # also runs check_drift_regenerate which would write CLAUDE.md; allow it.


def run_dispatcher(tmp):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = tmp
    return subprocess.run(
        [sys.executable, DISPATCHER],
        cwd=tmp, capture_output=True, text=True, env=env, input="{}"
    )


def strip_ansi(s):
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


# t18a: marker-file alert emits one brand-prefixed line
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    with open(os.path.join(td, ".rabbit-human-approval-bypass"), "w") as f:
        f.write("session")
    r = run_dispatcher(td)
    if r.returncode != 0:
        fail("18a", f"dispatcher exit {r.returncode}. stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout) if r.stdout.strip() else {}
        except json.JSONDecodeError as e:
            fail("18a", f"dispatcher stdout not JSON: {e}. stdout={r.stdout!r}")
            payload = {}
        msg = strip_ansi(payload.get("systemMessage", ""))
        alert_lines = [ln for ln in msg.split("\n")
                       if "HUMAN APPROVAL BYPASS" in ln]
        if len(alert_lines) != 1:
            fail("18a", f"expected exactly 1 alert line; got {len(alert_lines)}: {alert_lines!r}")
        elif not alert_lines[0].lstrip().startswith(BRAND):
            fail("18a", f"alert line not brand-prefixed: {alert_lines[0]!r}")
        else:
            ok("18a", "marker-file alert emits one brand-prefixed line")

# t18b: json-key alert emits one brand-prefixed line
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    settings = os.path.join(td, ".claude", "settings.local.json")
    with open(settings, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = run_dispatcher(td)
    if r.returncode != 0:
        fail("18b", f"dispatcher exit {r.returncode}. stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout) if r.stdout.strip() else {}
        except json.JSONDecodeError as e:
            fail("18b", f"dispatcher stdout not JSON: {e}. stdout={r.stdout!r}")
            payload = {}
        msg = strip_ansi(payload.get("systemMessage", ""))
        alert_lines = [ln for ln in msg.split("\n")
                       if "BYPASS-PERMISSIONS MODE ACTIVE" in ln]
        if len(alert_lines) != 1:
            fail("18b", f"expected exactly 1 alert line; got {len(alert_lines)}: {alert_lines!r}")
        elif not alert_lines[0].lstrip().startswith(BRAND):
            fail("18b", f"alert line not brand-prefixed: {alert_lines[0]!r}")
        else:
            ok("18b", "json-key alert emits one brand-prefixed line (reverse-map works)")

# t18c: no overrides — no alert lines
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    r = run_dispatcher(td)
    if r.returncode != 0:
        fail("18c", f"dispatcher exit {r.returncode}. stderr={r.stderr!r}")
    else:
        try:
            payload = json.loads(r.stdout) if r.stdout.strip() else {}
        except json.JSONDecodeError as e:
            fail("18c", f"dispatcher stdout not JSON: {e}. stdout={r.stdout!r}")
            payload = {}
        msg = strip_ansi(payload.get("systemMessage", ""))
        if "HUMAN APPROVAL BYPASS" in msg or "BYPASS-PERMISSIONS MODE ACTIVE" in msg:
            fail("18c", f"alert text appeared when no overrides active: {msg!r}")
        else:
            ok("18c", "no-override case: alert lines absent")

if FAIL:
    print("test-runtime-alerts-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-alerts-shape: all checks passed.")
