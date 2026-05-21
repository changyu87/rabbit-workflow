#!/usr/bin/env python3
"""test-rabbit-block-assembler.py — e2e tests for rabbit_block.

Verifies Inv 28(c): rabbit_block(*lines) -> '\\n' + '\\n'.join(lines).
This is the SINGLE authoritative place the leading newline lives — every
return value (including the empty case) starts with '\\n'.
"""

import os
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
MODULE_PATH = os.path.join(FEATURE_DIR, "scripts", "rabbit_print.py")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


spec = importlib.util.spec_from_file_location("rabbit_print", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

fn = getattr(mod, "rabbit_block", None)
if not callable(fn):
    fail("rabbit_block not callable")
    print("test-rabbit-block-assembler: FAIL", file=sys.stderr)
    sys.exit(1)
ok("rabbit_block is callable")

# Three lines
got = fn("a", "b", "c")
exp = "\n" + "\n".join(["a", "b", "c"])
if got == exp:
    ok("rabbit_block('a','b','c') == '\\n' + '\\n'.join([a,b,c])")
else:
    fail(f"three-line mismatch\n  exp: {exp!r}\n  got: {got!r}")
if got and got[0] == "\n":
    ok("rabbit_block three-line return starts with '\\n'")
else:
    fail(f"three-line return does not start with newline: {got!r}")

# Single line
got = fn("single")
exp = "\nsingle"
if got == exp:
    ok("rabbit_block('single') == '\\nsingle'")
else:
    fail(f"single-line mismatch\n  exp: {exp!r}\n  got: {got!r}")
if got[0] == "\n":
    ok("rabbit_block single-line return starts with '\\n'")
else:
    fail(f"single-line return does not start with newline: {got!r}")

# Zero lines
got = fn()
exp = "\n"
if got == exp:
    ok("rabbit_block() == '\\n'")
else:
    fail(f"zero-line mismatch\n  exp: {exp!r}\n  got: {got!r}")

# Many lines, with realistic rabbit-formatted lines
lines = [
    mod.welcome(),
    mod.rabbit_subline("policy loaded"),
    mod.rabbit_subline("ready"),
]
got = fn(*lines)
exp = "\n" + "\n".join(lines)
if got == exp:
    ok("rabbit_block(rendered-lines) == '\\n' + join(lines)")
else:
    fail(f"rendered-line block mismatch\n  exp: {exp!r}\n  got: {got!r}")
if got[0] == "\n":
    ok("rabbit_block rendered-line return starts with '\\n'")
else:
    fail(f"rendered-line return does not start with newline: {got!r}")

if FAIL != 0:
    print("test-rabbit-block-assembler: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-rabbit-block-assembler: all checks passed.")
