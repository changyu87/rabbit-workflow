#!/usr/bin/env python3
"""test-banner-suppression.py — Inv 14 end-to-end banner suppression contract.

When .rabbit-auto-evolve-active is present at the repo root, the SessionStart
and Stop dispatchers MUST emit the auto-evolve composite banner / stop-line.
When the marker is absent, the auto-evolve banner and stop-line are no-ops.

Scope note (#786): the per-configurable alert SUPPRESSION hook itself lives
in `contract.lib.runtime` (Inv 54, the `_AUTO_EVOLVE_SUPPRESSED_IDS` filter
inside iterate_configurables_*) and is owned by the `contract` feature — see
rabbit-auto-evolve/docs/spec.md "What this feature does NOT define". Its
coverage belongs to contract's own suite
(contract/test/test-runtime-iterate-configurables-alerts.py t12+). This rae
test therefore exercises only the rae-OWNED half of the suppression contract:
the auto-evolve composite banner + stop-line, which emit IN PLACE OF the
suppressed per-configurable alerts when the marker is present and are a no-op
when it is absent. It no longer imports the (now-dead, post rabbit-config
retirement) central iterate_configurables_alerts.

Test approach: build a synthetic .claude/features/ tree under a tempdir
containing a minimal rabbit-auto-evolve feature.json (no configurables —
only the runtime block) plus a copy of banner-status.py, then call the real
contract.lib.runtime banner/stop-line APIs in-process across four scenarios:

  S1: marker absent — banner returns [], stop-line returns [].
  S2: marker present + .rabbit/auto-evolve-state.json present (started-then-
      idle, #793) — banner returns 2 lines with default start hint as line 2;
      stop-line returns the active/idle steady line.
  S2b: marker present + state file ABSENT (post-`on`/pre-`start`, #793) — both
      surfaces emit the SAME restart-pending line so SessionStart and Stop
      agree: banner line 2 and the stop-line carry the verbatim
      'auto-evolve configured — restart Claude Code, then run /rabbit-auto-evolve start'.
  S3: marker + .rabbit-auto-evolve-restart-needed — banner line 2 is
      the restart-resume hint substring.
  S4: marker + .rabbit-auto-evolve-aborted (highest precedence) — banner
      line 2 contains 'loop aborted on safety violation' substring.

Imports contract.lib.runtime directly via sys.path injection (same pattern
as contract/test/test-runtime-emit-auto-evolve-banner.py). No shell-outs.
"""

import json
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CONTRACT_DIR = os.path.join(REPO_ROOT, ".claude", "features", "contract")
sys.path.insert(0, CONTRACT_DIR)

# Source banner-status.py — emit_auto_evolve_banner now delegates line-1
# and line-2 content to this script via subprocess (PR #383). The synthetic
# tempdir tree must contain this script under
# .claude/features/rabbit-auto-evolve/scripts/banner-status.py so the
# subprocess call resolves; otherwise the banner returns [] for every
# scenario.
BANNER_STATUS_SRC = os.path.join(
    REPO_ROOT,
    ".claude", "features", "rabbit-auto-evolve",
    "scripts", "banner-status.py",
)

from lib.runtime import (  # noqa: E402
    emit_auto_evolve_banner,
    emit_auto_evolve_stop_line,
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
    ae_dir = os.path.join(td, ".claude", "features", "rabbit-auto-evolve")
    os.makedirs(ae_dir, exist_ok=True)
    with open(os.path.join(ae_dir, "feature.json"), "w") as f:
        json.dump(RABBIT_AUTO_EVOLVE_FJ, f)
    # Copy banner-status.py into the synthetic tempdir so the subprocess
    # invocation inside emit_auto_evolve_banner resolves (PR #383 delegation).
    scripts_dir = os.path.join(ae_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    shutil.copy2(BANNER_STATUS_SRC,
                 os.path.join(scripts_dir, "banner-status.py"))


# S1: marker absent — banner and stop-line are both no-ops
with tempfile.TemporaryDirectory() as td:
    build_repo(td)
    banner = emit_auto_evolve_banner(repo_root=td)
    stop = emit_auto_evolve_stop_line(repo_root=td)
    if banner != []:
        fail(f"S1: expected banner == [] when marker absent, got {banner!r}")
    elif stop != []:
        fail(f"S1: expected stop == [] when marker absent, got {stop!r}")
    else:
        ok("S1: marker absent -> banner and stop-line are no-ops")

# S2 (#793): marker present + state file present (started-then-idle) — banner
# emits 2 lines with default start hint, and the stop-line emits the active/idle
# steady state line. This composite surface is what replaces the suppressed
# per-configurable alerts under auto-evolve.
with tempfile.TemporaryDirectory() as td:
    build_repo(td)
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, os.path.join(".rabbit", "auto-evolve-state.json"), "{}")
    banner = emit_auto_evolve_banner(repo_root=td)
    stop = emit_auto_evolve_stop_line(repo_root=td)
    if len(banner) != 2:
        fail(f"S2: expected banner with 2 entries, got {len(banner)}: {banner!r}")
    elif "AUTONOMOUS-EVOLVE MODE ACTIVE" not in banner[0].get("text", ""):
        fail(f"S2: banner line 1 missing AUTONOMOUS-EVOLVE MODE ACTIVE; "
             f"got {banner[0]!r}")
    elif "/rabbit-auto-evolve start" not in banner[1].get("text", ""):
        fail(f"S2: banner line 2 missing '/rabbit-auto-evolve start' default "
             f"start hint; got {banner[1]!r}")
    elif len(stop) != 1:
        fail(f"S2: expected stop-line with 1 entry, got {len(stop)}: {stop!r}")
    elif "auto-evolve loop active" not in stop[0].get("text", ""):
        fail(f"S2: stop-line missing active/idle steady substring; "
             f"got {stop[0]!r}")
    else:
        ok("S2: marker + state file -> composite banner + active stop-line emit")

# S2b (#793): marker present + state file ABSENT (post-`on`/pre-`start` window)
# — both the SessionStart banner line 2 and the Stop line carry the SAME
# verbatim restart-pending text so the two surfaces agree.
RESTART_PENDING = (
    "auto-evolve configured — restart Claude Code, then run "
    "/rabbit-auto-evolve start"
)
with tempfile.TemporaryDirectory() as td:
    build_repo(td)
    touch(td, ".rabbit-auto-evolve-active")  # state file deliberately absent
    banner = emit_auto_evolve_banner(repo_root=td)
    stop = emit_auto_evolve_stop_line(repo_root=td)
    if len(banner) != 2:
        fail(f"S2b: expected banner with 2 entries, got {len(banner)}: {banner!r}")
    elif banner[1].get("text") != RESTART_PENDING:
        fail(f"S2b: banner line 2 != restart-pending verbatim; got {banner[1]!r}")
    elif len(stop) != 1:
        fail(f"S2b: expected stop-line with 1 entry, got {len(stop)}: {stop!r}")
    elif stop[0].get("text") != RESTART_PENDING:
        fail(f"S2b: stop-line != restart-pending verbatim; got {stop[0]!r}")
    else:
        ok("S2b: state file absent -> banner and stop-line agree on restart-pending")

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
