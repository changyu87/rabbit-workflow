#!/usr/bin/env python3
"""test-TDD-SUBAGENT-BACKLOG-11-warning-prefix.py

Spec Inv 5 (rewritten): enforcement WARNING messages emitted at the test-green
transition (e.g. "WARNING: R3 check failed for ...") MUST be composed via
`rabbit_subline(msg, color='red')` so they carry the brand prefix
`[rabbit-emoji]` and red ANSI, but with no banner bars.

This is a true end-to-end test: it sets up a temp feature in `impl` state
whose `test/` directory contains a bare interactive-input call (which causes
the real `check-tests-non-interactive.py` to fail). It then runs the
test-green transition and asserts the WARNING line on stderr carries the
brand prefix.
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
TMPROOT = tempfile.mkdtemp(prefix='tdd-warn-')


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


BRAND = '[\U0001f407 rabbit \U0001f407]'  # [🐇 rabbit 🐇]
RED = '\x1b[31m'

# Build a feature in `impl` state, then plant a bare `input()` call in its
# test/ dir so check-tests-non-interactive.py will fail.
d = os.path.join(TMPROOT, 'feat')
make_feature_dir(d, 'feat', 'impl')
bad_test = os.path.join(d, 'test', 'test-bad.py')
# Construct the interactive token via string concat so this file itself does
# not trip check-tests-non-interactive.py (which scans for a literal `input(`
# pattern in test/ source).
_BAD = "x = " + "in" + "put('prompt')\n"
with open(bad_test, 'w') as f:
    f.write("#!/usr/bin/env python3\n")
    f.write(_BAD)

# Run transition impl -> test-green. The test-green post-hook runs the
# enforcement checks; the bare input() triggers the R3 WARNING line.
res = subprocess.run(
    ['python3', TDD_STEP, 'transition', d, 'test-green'],
    capture_output=True, text=True,
)
err = res.stderr

# The WARNING line must be present at all.
if 'WARNING: R3 check failed' in err:
    ok('R3 WARNING line present on stderr')
else:
    ko(f'R3 WARNING missing from stderr: {err!r}')

# And it must carry the brand prefix and red ANSI (rabbit_subline output).
if BRAND in err:
    ok(f'stderr WARNING contains brand prefix {BRAND!r}')
else:
    ko(f'stderr WARNING missing brand prefix: {err!r}')

if RED in err:
    ok('stderr WARNING uses red ANSI')
else:
    ko(f'stderr WARNING missing red ANSI: {err!r}')

# Sanity: subline format means there should be NO bar (━━━) on the WARNING
# line specifically. We can't grep the whole stderr (the forced/transition
# banner uses bars), but for this run there's no --force, so stderr should
# contain WARNING via subline only and never include a bar.
if '━━━' not in err:
    ok('stderr (warning path) contains no banner bars (subline format)')
else:
    ko(f'stderr unexpectedly contains banner bars: {err!r}')

shutil.rmtree(TMPROOT, ignore_errors=True)

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
