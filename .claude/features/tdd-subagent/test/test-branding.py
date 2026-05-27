#!/usr/bin/env python3
# test-branding.py — Inv 9 coverage.
#
# Inv 9: tdd-step.py renders every transition message through rabbit_print.
#   Accepted transitions: rabbit_print("{CUR} -> {NEW}", "🔧", "green") on
#     stdout (ANSI green, [🐇 rabbit 🐇] brand).
#   Forced transitions: rabbit_print("FORCED: {CUR} -> {NEW}", "🔧", "red")
#     on stderr (ANSI red).
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')
TMPROOT = tempfile.mkdtemp()

sys.path.insert(0, SCRIPT_DIR)
from state_machine_helpers import make_feature_dir as _make_feature_dir  # noqa: E402

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def run(*args):
    stdout_f = os.path.join(TMPROOT, 'stdout')
    stderr_f = os.path.join(TMPROOT, 'stderr')
    with open(stdout_f, 'wb') as out, open(stderr_f, 'wb') as err:
        subprocess.run(['python3', TDD_STEP] + list(args), stdout=out, stderr=err)


def stdout_bytes():
    with open(os.path.join(TMPROOT, 'stdout'), 'rb') as f:
        return f.read()


def stderr_bytes():
    with open(os.path.join(TMPROOT, 'stderr'), 'rb') as f:
        return f.read()


# Inv 9: transition stdout contains the [rabbit] brand.
def t_brand_stdout():
    d = os.path.join(TMPROOT, 't_brand')
    _make_feature_dir(d, 't_brand', 'spec')
    run('transition', d, 'spec-update')
    out = stdout_bytes().decode(errors='replace')
    if '[\U0001f407 rabbit \U0001f407]' in out:
        ok('Inv 9: transition stdout contains [rabbit] brand')
    else:
        ko(f"brand: not found in stdout: '{out}'")


# Inv 9: accepted transition stdout contains ANSI green code.
def t_ansi_green_stdout():
    d = os.path.join(TMPROOT, 't_green')
    _make_feature_dir(d, 't_green', 'spec')
    run('transition', d, 'spec-update')
    if b'\x1b[32m' in stdout_bytes():
        ok('Inv 9: accepted transition stdout contains ANSI green (\\x1b[32m)')
    else:
        ko('green: ANSI green not found in stdout')


# Inv 9: forced transition stderr contains ANSI red code.
def t_ansi_red_stderr():
    d = os.path.join(TMPROOT, 't_red')
    _make_feature_dir(d, 't_red', 'impl')
    run('transition', d, 'test-red', '--force')
    if b'\x1b[31m' in stderr_bytes():
        ok('Inv 9: forced transition stderr contains ANSI red (\\x1b[31m)')
    else:
        ko('red: ANSI red not found in stderr')


print(f"running branding tests against {TDD_STEP}")
t_brand_stdout(); t_ansi_green_stdout(); t_ansi_red_stderr()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
