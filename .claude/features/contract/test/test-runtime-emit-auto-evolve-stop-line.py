#!/usr/bin/env python3
"""test-runtime-emit-auto-evolve-stop-line.py — exercises
emit_auto_evolve_stop_line per Inv 65. Returns [] only when
.rabbit-auto-evolve-active is absent (the marker gates the whole composite
surface). When active, returns exactly ONE entry: a state marker (strict
priority aborted > restart-needed > stop-requested > running) wins when
present; otherwise the steady active/idle line is emitted.
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
    with open(os.path.join(root, name), "w") as f:
        f.write("")


ABORTED = ("auto-evolve loop aborted — see .rabbit/auto-evolve-state.json",
           "⛔", "red")
RESTART = ("auto-evolve loop awaiting restart", "⏸", "yellow")
STOP_REQ = ("auto-evolve loop stop requested — will exit on next tick",
            "⏸", "yellow")
RUNNING = ("auto-evolve loop running", "🔁", "green")
ACTIVE_IDLE = ("auto-evolve loop active — idle between ticks", "🔁", "green")


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

# F: active only (no state markers) -> exactly one steady active/idle entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ACTIVE_IDLE, "F")

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

if FAIL:
    print("test-runtime-emit-auto-evolve-stop-line: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-auto-evolve-stop-line: all checks passed.")
