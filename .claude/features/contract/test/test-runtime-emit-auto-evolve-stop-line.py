#!/usr/bin/env python3
"""test-runtime-emit-auto-evolve-stop-line.py — exercises
emit_auto_evolve_stop_line per Inv 55. Returns [] only when
.rabbit-auto-evolve-active is absent (the marker gates the whole composite
surface). When active, returns exactly ONE entry: a state marker (strict
priority aborted > restart-needed > stop-requested > running) wins when
present; otherwise the fall-through distinguishes the never-started window
(no .rabbit/auto-evolve-state.json -> restart-pending line, #793) from the
started-and-idle steady state (state file present -> idle line).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import emit_auto_evolve_stop_line  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def touch(root, name):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w") as f:
        f.write("")


def write_state_file(root):
    """Create .rabbit/auto-evolve-state.json (loop started at least once)."""
    rabbit_dir = os.path.join(root, ".rabbit")
    os.makedirs(rabbit_dir, exist_ok=True)
    with open(os.path.join(rabbit_dir, "auto-evolve-state.json"), "w") as f:
        f.write("{}")


ABORTED = ("auto-evolve loop aborted — see .rabbit/auto-evolve-state.json",
           "⛔", "red")
RESTART = ("auto-evolve loop awaiting restart", "⏸", "yellow")
STOP_REQ = ("auto-evolve loop stop requested — will exit on next tick",
            "⏸", "yellow")
RUNNING = ("auto-evolve loop running", "🔁", "green")
ACTIVE_IDLE = ("auto-evolve loop active — idle between ticks", "🔁", "green")
RESTART_PENDING = (
    "auto-evolve configured — restart Claude Code, then run /rabbit-auto-evolve start",
    "⏸", "yellow")


def assert_one(r, expected, label):
    text, icon, color = expected
    if len(r) != 1:
        fail(f"{label}: expected 1 entry, got {r!r}")
        return
    e = r[0]
    if e["type"] != "print" or e["text"] != text \
            or e["icon"] != icon or e["color"] != color:
        fail(f"{label}: entry wrong: {e!r} (expected text={text!r} icon={icon!r} color={color!r})")
        return
    ok(f"{label}: emitted {text!r}")


# A: no active marker -> []
with tempfile.TemporaryDirectory() as td:
    r = emit_auto_evolve_stop_line(repo_root=td)
    if r == []:
        ok("A: active marker absent returns []")
    else:
        fail(f"A: expected [], got {r!r}")

# B: active + aborted -> aborted entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ABORTED, "B")

# C: active + restart-needed -> restart entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-restart-needed")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RESTART, "C")

# D: active + stop-requested -> stop-requested entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-stop-requested")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, STOP_REQ, "D")

# E: active + running -> running entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RUNNING, "E")

# F: active only, NO state file (never started, post-on/pre-start window, #793)
#    -> exactly one restart-pending entry (NOT the idle line)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RESTART_PENDING, "F")

# F2: active + state file present (loop started at least once), no state markers
#     -> the steady active/idle entry (unchanged)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ACTIVE_IDLE, "F2")

# G (precedence): active + aborted + running -> aborted wins
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ABORTED, "G")

# H (precedence): active + restart-needed + stop-requested + running -> restart wins
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-restart-needed")
    touch(td, ".rabbit-auto-evolve-stop-requested")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RESTART, "H")

# I (precedence): active + stop-requested + running -> stop-requested wins
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-stop-requested")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, STOP_REQ, "I")

# J: active marker absent but other state markers present -> still []
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-running")
    touch(td, ".rabbit-auto-evolve-aborted")
    r = emit_auto_evolve_stop_line(repo_root=td)
    if r == []:
        ok("J: active absent gates whole surface, returns [] regardless of state markers")
    else:
        fail(f"J: expected [], got {r!r}")

# K: a state marker wins over the restart-pending fall-through even when the
#    state file is ABSENT (never-started window): active + running + no state
#    file -> running (state markers take strict priority over fall-through)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RUNNING, "K")

# L: a state marker wins regardless of state file PRESENCE too: active +
#    aborted + state file present -> aborted
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    write_state_file(td)
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ABORTED, "L")

if FAIL:
    print("test-runtime-emit-auto-evolve-stop-line: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-auto-evolve-stop-line: all checks passed.")
