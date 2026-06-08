#!/usr/bin/env python3
"""test-runtime-vendored-marker-roots.py — Inv 68: decouple the FEATURES root
from the REPO-ROOT MARKERS root in contract.lib.runtime.

In a VENDORED install the framework features live at
`<git-toplevel>/.rabbit/.claude/features`, so the dispatcher resolves
`repo_root` to `RABBIT_ROOT` = the `.rabbit` install dir. feature.json
resolution against that `repo_root` is CORRECT. But repo-root markers like
`.rabbit-tdd-autonomous` are written at the GIT TOPLEVEL (the host project,
parent of `.rabbit`), so they MUST be READ at the git toplevel — not at
`repo_root/.rabbit-tdd-autonomous` (= `<host>/.rabbit/.rabbit-tdd-autonomous`,
which never exists).

#1048: the single `repo_root` arg conflated the two roots, so the Step-4
autonomous check false-negatived in vendored mode (marker present at the
toplevel, but read one `.rabbit` too deep -> autonomous-OFF). This test
simulates a vendored layout and asserts emit_configurable_alert reads the
marker at the git toplevel while resolving feature.json inside `.rabbit`.
Standalone layout (basename != .rabbit) is asserted UNCHANGED.
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


# tdd-autonomous configurable (post-#336 flipped polarity): values.true =>
# write_marker (present = autonomous active), values.false => delete_marker.
TDD_AUTO_CONF = {
    "id": "tdd-autonomous",
    "subcommand": "tdd-autonomous",
    "storage": {"type": "marker-file", "path": ".rabbit-tdd-autonomous"},
    "values": {"false": {"api": "delete_marker",
                         "args": {"path": ".rabbit-tdd-autonomous"}},
               "true": {"api": "write_marker",
                        "args": {"path": ".rabbit-tdd-autonomous",
                                 "content": "session"}}},
    "default": "false",
    "alert-on": "true",
    "alert-message": {"text": "TDD AUTONOMOUS MODE ACTIVE",
                      "icon": "robot", "color": "yellow"},
}


def make_feature_at(features_root, name, configuration):
    fdir = os.path.join(features_root, name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": name, "version": "1.0.0", "owner": "x",
                   "configuration": configuration}, f)


# --- VENDORED layout -------------------------------------------------------
# git toplevel = <td>; rabbit install (repo_root passed by dispatcher) =
# <td>/.rabbit ; features live at <td>/.rabbit/.claude/features ; the
# /rabbit-tdd-autonomous marker is written at the GIT TOPLEVEL <td>.

# t1 (#1048): vendored, marker PRESENT at the git toplevel -> alert FIRES.
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    features_root = os.path.join(rabbit_root, ".claude", "features")
    make_feature_at(features_root, "rabbit-feature", [TDD_AUTO_CONF])
    # An extra entry alongside `.rabbit` so detect_mode sees a vendored host.
    os.makedirs(os.path.join(td, "src"), exist_ok=True)
    # Marker written at the GIT TOPLEVEL (where /rabbit-tdd-autonomous writes).
    with open(os.path.join(td, ".rabbit-tdd-autonomous"), "w") as f:
        f.write("session")
    r = emit_configurable_alert("rabbit-feature", "tdd-autonomous",
                                repo_root=rabbit_root)
    if (r.get("type") == "print"
            and r.get("text") == "TDD AUTONOMOUS MODE ACTIVE"):
        ok("t1: vendored marker at git toplevel -> alert FIRES (feature.json "
           "resolved inside .rabbit)")
    else:
        fail(f"t1: expected print_result (marker read at toplevel), got {r!r}")

# t2 (#1048): vendored, NO marker anywhere -> silent (ok_result).
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    features_root = os.path.join(rabbit_root, ".claude", "features")
    make_feature_at(features_root, "rabbit-feature", [TDD_AUTO_CONF])
    os.makedirs(os.path.join(td, "src"), exist_ok=True)
    r = emit_configurable_alert("rabbit-feature", "tdd-autonomous",
                                repo_root=rabbit_root)
    if r == {"type": "ok"}:
        ok("t2: vendored, no marker -> silent (ok_result)")
    else:
        fail(f"t2: expected ok_result, got {r!r}")

# t3 (#1048): vendored, a stale marker INSIDE .rabbit must NOT be honoured —
# only the git-toplevel location is the read site.
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    features_root = os.path.join(rabbit_root, ".claude", "features")
    make_feature_at(features_root, "rabbit-feature", [TDD_AUTO_CONF])
    os.makedirs(os.path.join(td, "src"), exist_ok=True)
    # Wrong location (one .rabbit too deep) — must be ignored.
    with open(os.path.join(rabbit_root, ".rabbit-tdd-autonomous"), "w") as f:
        f.write("session")
    r = emit_configurable_alert("rabbit-feature", "tdd-autonomous",
                                repo_root=rabbit_root)
    if r == {"type": "ok"}:
        ok("t3: vendored, marker only inside .rabbit (wrong site) -> silent")
    else:
        fail(f"t3: expected ok_result (stale-inside-.rabbit ignored), got {r!r}")

# --- STANDALONE layout (UNCHANGED) ----------------------------------------
# git toplevel == repo_root (basename != .rabbit); features and markers both
# live under it directly.

# t4: standalone, marker PRESENT at repo_root -> alert FIRES (regression-safe).
with tempfile.TemporaryDirectory() as td:
    features_root = os.path.join(td, ".claude", "features")
    make_feature_at(features_root, "rabbit-feature", [TDD_AUTO_CONF])
    with open(os.path.join(td, ".rabbit-tdd-autonomous"), "w") as f:
        f.write("session")
    r = emit_configurable_alert("rabbit-feature", "tdd-autonomous",
                                repo_root=td)
    if (r.get("type") == "print"
            and r.get("text") == "TDD AUTONOMOUS MODE ACTIVE"):
        ok("t4: standalone marker at repo_root -> alert FIRES (unchanged)")
    else:
        fail(f"t4: expected print_result, got {r!r}")

# t5: standalone, NO marker -> silent (regression-safe).
with tempfile.TemporaryDirectory() as td:
    features_root = os.path.join(td, ".claude", "features")
    make_feature_at(features_root, "rabbit-feature", [TDD_AUTO_CONF])
    r = emit_configurable_alert("rabbit-feature", "tdd-autonomous",
                                repo_root=td)
    if r == {"type": "ok"}:
        ok("t5: standalone, no marker -> silent (unchanged)")
    else:
        fail(f"t5: expected ok_result, got {r!r}")

if FAIL:
    print("test-runtime-vendored-marker-roots: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-vendored-marker-roots: all checks passed.")
