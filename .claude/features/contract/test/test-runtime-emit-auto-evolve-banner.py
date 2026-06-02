#!/usr/bin/env python3
"""test-runtime-emit-auto-evolve-banner.py — exercises emit_auto_evolve_banner
per Inv 65. Returns [] when .rabbit-auto-evolve-active is absent; otherwise
2 entries: line 1 always (the AUTONOMOUS-EVOLVE MODE ACTIVE headline) plus
line 2 chosen by marker priority (aborted > restart-needed > default).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import emit_auto_evolve_banner  # noqa: E402

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


LINE1_TEXT = ("AUTONOMOUS-EVOLVE MODE ACTIVE — loop will dispatch TDD "
              "subagents and merge to dev without prompts")
DEFAULT_LINE2 = "to start the loop, paste: /rabbit-auto-evolve start"
RESTART_LINE2 = "resume after restart: paste /rabbit-auto-evolve start"
ABORTED_LINE2 = ("loop aborted on safety violation — see "
                 ".rabbit/auto-evolve-state.json and clear marker to resume")


# A: no .rabbit-auto-evolve-active marker -> []
with tempfile.TemporaryDirectory() as td:
    r = emit_auto_evolve_banner(repo_root=td)
    if r == []:
        ok("A: marker absent returns []")
    else:
        fail(f"A: expected [], got {r!r}")

# B: active marker only -> 2 entries; line 1 + default line 2
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    r = emit_auto_evolve_banner(repo_root=td)
    if len(r) != 2:
        fail(f"B: expected 2 entries, got {r!r}")
    elif r[0]["type"] != "print" or r[0]["text"] != LINE1_TEXT \
            or r[0]["icon"] != "✨" or r[0]["color"] != "red":
        fail(f"B: line 1 wrong: {r[0]!r}")
    elif r[1]["type"] != "print" or r[1]["text"] != DEFAULT_LINE2 \
            or r[1]["icon"] != "▶" or r[1]["color"] != "yellow":
        fail(f"B: default line 2 wrong: {r[1]!r}")
    else:
        ok("B: active marker only -> 2 entries (headline + default start hint)")

# C: active + restart-needed -> line 2 is restart variant
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-restart-needed")
    r = emit_auto_evolve_banner(repo_root=td)
    if len(r) != 2:
        fail(f"C: expected 2 entries, got {r!r}")
    elif r[1]["text"] != RESTART_LINE2 or r[1]["icon"] != "▶" \
            or r[1]["color"] != "yellow":
        fail(f"C: restart variant wrong: {r[1]!r}")
    else:
        ok("C: active+restart-needed -> restart-resume hint")

# D: active + aborted -> line 2 is aborted variant
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    r = emit_auto_evolve_banner(repo_root=td)
    if len(r) != 2:
        fail(f"D: expected 2 entries, got {r!r}")
    elif r[1]["text"] != ABORTED_LINE2 or r[1]["icon"] != "⛔" \
            or r[1]["color"] != "yellow":
        fail(f"D: aborted variant wrong: {r[1]!r}")
    else:
        ok("D: active+aborted -> aborted variant")

# E (precedence): active + aborted + restart-needed -> aborted wins
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    touch(td, ".rabbit-auto-evolve-restart-needed")
    r = emit_auto_evolve_banner(repo_root=td)
    if len(r) != 2:
        fail(f"E: expected 2 entries, got {r!r}")
    elif r[1]["text"] != ABORTED_LINE2:
        fail(f"E: precedence violated — expected aborted variant, got {r[1]!r}")
    else:
        ok("E: aborted wins over restart-needed when both present")

if FAIL:
    print("test-runtime-emit-auto-evolve-banner: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-auto-evolve-banner: all checks passed.")
