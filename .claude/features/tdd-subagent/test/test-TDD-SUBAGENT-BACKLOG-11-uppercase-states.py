#!/usr/bin/env python3
"""test-TDD-SUBAGENT-BACKLOG-11-uppercase-states.py

Spec Inv 5 (rewritten): tdd-step.py transition output uses the centralized
rabbit_print renderer. State names appear UPPERCASE in the rendered output:
`[🐇 rabbit 🐇] 🔧 ━━━ FROM_STATE -> TO_STATE ━━━ 🔧`.

Normal transitions go to stdout (green); forced transitions also emit a red
alert line to stderr.

This is a true end-to-end test: it invokes tdd-step.py via subprocess against
a real temp feature directory created via the shared test_helpers fixture.
"""
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')

sys.path.insert(0, SCRIPT_DIR)
from test_helpers import make_feature_dir  # noqa: E402

PASS = 0
FAIL = 0
TMPROOT = tempfile.mkdtemp(prefix='tdd-upper-')


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def run(*args):
    res = subprocess.run(
        ['python3', TDD_STEP] + list(args),
        capture_output=True, text=True,
    )
    return res.returncode, res.stdout, res.stderr


BRAND = '[\U0001f407 rabbit \U0001f407]'  # [🐇 rabbit 🐇]
ICON = '\U0001f527'                         # 🔧
GREEN = '\x1b[32m'
RED = '\x1b[31m'

# ---------- Normal transition: spec -> spec-update ----------
d1 = os.path.join(TMPROOT, 'norm')
make_feature_dir(d1, 'norm', 'spec')
rc, out, err = run('transition', d1, 'spec-update')
if rc == 0:
    ok('normal transition spec -> spec-update exit 0')
else:
    ko(f'normal transition exit {rc}, stderr={err!r}')

# Uppercase state names appear in stdout
if 'SPEC -> SPEC-UPDATE' in out:
    ok('stdout contains uppercase "SPEC -> SPEC-UPDATE"')
else:
    ko(f'stdout missing uppercase state names: {out!r}')

# Lowercase forms must NOT be present in the transition line.
if 'spec -> spec-update' not in out:
    ok('stdout does not contain lowercase "spec -> spec-update"')
else:
    ko(f'stdout still contains lowercase form: {out!r}')

# Brand and icon present.
if BRAND in out:
    ok(f'stdout contains brand {BRAND!r}')
else:
    ko(f'stdout missing brand: {out!r}')

if ICON in out:
    ok('stdout contains 🔧 icon')
else:
    ko(f'stdout missing icon: {out!r}')

if GREEN in out:
    ok('stdout uses green ANSI for normal transition')
else:
    ko(f'stdout missing green ANSI: {out!r}')

# rabbit_block contract (Inv 5, contract Inv 36): output starts with a
# leading newline so the [🐇 rabbit 🐇] banner renders on its own row,
# not inline with surrounding chrome. The ANSI color prefix sits between
# the newline and the brand text.
if out.startswith('\n') and out.split('\n', 1)[1].startswith(GREEN + BRAND):
    ok('stdout starts with leading newline + ANSI + brand (rabbit_block contract)')
else:
    ko(f'stdout does not start with newline+ANSI+brand: {out[:80]!r}')

# ---------- Forced transition: impl -> test-red ----------
d2 = os.path.join(TMPROOT, 'forced')
make_feature_dir(d2, 'forced', 'impl')
rc, out, err = run('transition', d2, 'test-red', '--force')
if rc == 0:
    ok('forced transition exit 0')
else:
    ko(f'forced transition exit {rc}')

# Forced alert goes to STDERR with red ANSI.
if RED in err:
    ok('stderr (forced) uses red ANSI')
else:
    ko(f'stderr missing red ANSI: {err!r}')

if 'FORCED: IMPL -> TEST-RED' in err:
    ok('stderr contains uppercase "FORCED: IMPL -> TEST-RED"')
else:
    ko(f'stderr missing uppercase forced line: {err!r}')

if BRAND in err:
    ok('stderr (forced) contains brand prefix')
else:
    ko(f'stderr missing brand: {err!r}')

# The normal-style transition line still emitted to stdout in green.
if GREEN in out and 'IMPL -> TEST-RED' in out:
    ok('stdout (forced cycle) still emits green uppercase transition line')
else:
    ko(f'stdout missing green uppercase line on forced: {out!r}')

# Both stdout (transition line) and stderr (forced alert) start with the
# rabbit_block leading newline + ANSI + brand.
if out.startswith('\n') and out.split('\n', 1)[1].startswith(GREEN + BRAND):
    ok('stdout (forced) starts with leading newline + ANSI + brand')
else:
    ko(f'stdout (forced) does not start with newline+ANSI+brand: {out[:80]!r}')
if err.startswith('\n') and err.split('\n', 1)[1].startswith(RED + BRAND):
    ok('stderr (forced) starts with leading newline + ANSI + brand')
else:
    ko(f'stderr (forced) does not start with newline+ANSI+brand: {err[:80]!r}')

# ---------- Cleanup ----------
shutil.rmtree(TMPROOT, ignore_errors=True)

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
