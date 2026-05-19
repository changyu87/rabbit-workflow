#!/usr/bin/env python3
# test-wave4-bug6-12-46-51.py
#
# Wave 4 fixes:
# BUG-6/12/46: tdd-step.py auto_close_backlog must call rabbit-file's item-status.py,
#              not the deleted backlog-item-status.py.
# BUG-51:      tdd-step.py state machine must accept test-green -> spec-update
#              (cycle restart) as a valid forward transition alongside the existing
#              test-green -> deprecated (retirement) transition.
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')
TMPROOT = tempfile.mkdtemp()

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


def fix(d, n, s):
    os.makedirs(d, exist_ok=True)
    feature_json = {
        "name": n,
        "version": "0.1.0",
        "owner": {"primary": "test", "contact": ""},
        "status": "active",
        "tdd_state": s,
        "deprecation": {"criterion": "fixture", "successor": None},
        "contract": {"reads": [], "writes": [], "invokes": []},
        "created": "2026-05-18",
        "updated": "2026-05-18",
    }
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        json.dump(feature_json, f, indent=2)


def run(*args, env=None):
    stdout_f = os.path.join(TMPROOT, 'stdout')
    stderr_f = os.path.join(TMPROOT, 'stderr')
    full_env = {**os.environ, **(env or {})}
    with open(stdout_f, 'wb') as out, open(stderr_f, 'wb') as err:
        result = subprocess.run(
            ['python3', TDD_STEP] + list(args),
            stdout=out, stderr=err, env=full_env,
        )
    return result.returncode


def read_out():
    with open(os.path.join(TMPROOT, 'stdout')) as f:
        return f.read().strip()


def read_err():
    with open(os.path.join(TMPROOT, 'stderr')) as f:
        return f.read().strip()


# bug6_static_no_backlog_item_status: tdd-step.py source must not reference
# the deleted backlog-item-status.py script name.
def t_bug6_static_no_backlog_item_status():
    with open(TDD_STEP) as f:
        content = f.read()
    if 'backlog-item-status.py' not in content:
        ok('bug6: tdd-step.py no longer references deleted backlog-item-status.py')
    else:
        ko('bug6: tdd-step.py still references backlog-item-status.py (must use item-status.py)')


# NOTE (BACKLOG-13): bug6_static_uses_item_status and bug6_static_set_type_backlog
# were retired alongside the legacy local backlog scan in auto_close_backlog.
# Discovery + closing of in-progress backlog items is now the dispatcher's
# responsibility (dispatch-tdd-subagent.py --linked-item / --linked-items),
# not tdd-step.py's. The remaining bug6 check (no reference to the deleted
# backlog-item-status.py script) stays — that script must never reappear.


# bug51_test_green_to_spec_update_allowed: cycle restart must be a forward
# transition (no --force).
def t_bug51_test_green_to_spec_update_allowed():
    d = os.path.join(TMPROOT, 'bug51a')
    fix(d, 'bug51a', 'test-green')
    rc = run('transition', d, 'spec-update')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'spec-update':
        ok('bug51: test-green -> spec-update accepted as forward transition (cycle restart)')
    else:
        ko(f'bug51: rc={rc} newstate={newstate} stderr={read_err()}')


# bug51_test_green_to_deprecated_still_allowed: retirement path still works.
def t_bug51_test_green_to_deprecated_still_allowed():
    d = os.path.join(TMPROOT, 'bug51b')
    fix(d, 'bug51b', 'test-green')
    rc = run('transition', d, 'deprecated')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'deprecated':
        ok('bug51: test-green -> deprecated still accepted as forward transition (retirement)')
    else:
        ko(f'bug51: rc={rc} newstate={newstate} stderr={read_err()}')


# bug51_test_green_to_test_red_denied: test-red is NOT a valid forward from test-green.
def t_bug51_test_green_to_test_red_denied():
    d = os.path.join(TMPROOT, 'bug51c')
    fix(d, 'bug51c', 'test-green')
    rc = run('transition', d, 'test-red')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'test-green':
        ok('bug51: test-green -> test-red denied without --force (not a valid forward)')
    else:
        ko(f'bug51: rc={rc} newstate={newstate} stderr={read_err()}')


# bug51_transitions_lists_both_options: `tdd-step.py transitions` must list both
# spec-update and deprecated for a test-green starting state.
def t_bug51_transitions_lists_both_options():
    d = os.path.join(TMPROOT, 'bug51d')
    fix(d, 'bug51d', 'test-green')
    rc = run('transitions', d)
    out = read_out()
    if rc == 0 and 'spec-update' in out and 'deprecated' in out:
        ok('bug51: transitions from test-green lists both spec-update and deprecated')
    else:
        ko(f'bug51: rc={rc} out={out!r} (expected both spec-update and deprecated)')


print(f"running Wave 4 (BUG-6/12/46/51) tests against {TDD_STEP}")
t_bug6_static_no_backlog_item_status()
t_bug51_test_green_to_spec_update_allowed()
t_bug51_test_green_to_deprecated_still_allowed()
t_bug51_test_green_to_test_red_denied()
t_bug51_transitions_lists_both_options()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
