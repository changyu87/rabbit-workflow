#!/usr/bin/env python3
# test-state-machine.py — Inv 31-35 end-to-end coverage (8-step cycle).
#
# Inv 31: Valid state set = {spec, spec-update, test-red, impl,
#         sync-deployed, test-green, deprecated}.
# Inv 32: Primary forward order
#         spec -> spec-update -> test-red -> impl -> sync-deployed ->
#         test-green -> deprecated.
# Inv 33: Alternate forward edge test-green -> spec-update (no --force).
# Inv 34: Non-forward transitions require --force.
# Inv 35: deprecated is terminal; --force does not override.
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


def fix(d, n, s):
    _make_feature_dir(d, n, s)


def run(*args):
    stdout_f = os.path.join(TMPROOT, 'stdout')
    stderr_f = os.path.join(TMPROOT, 'stderr')
    with open(stdout_f, 'wb') as out, open(stderr_f, 'wb') as err:
        result = subprocess.run(['python3', TDD_STEP] + list(args), stdout=out, stderr=err)
    return result.returncode


def read_out():
    with open(os.path.join(TMPROOT, 'stdout')) as f:
        return f.read().strip()


def read_err():
    with open(os.path.join(TMPROOT, 'stderr')) as f:
        return f.read().strip()


# Inv 1: show returns current state (basic state set sanity).
def t_show():
    d = os.path.join(TMPROOT, 't_show')
    fix(d, 't_show', 'spec')
    rc = run('show', d)
    out = read_out()
    if rc == 0 and out == 'spec':
        ok('show: returns current state "spec"')
    else:
        ko(f"show: rc={rc} out='{out}'")


# Inv 1: invalid target state denied.
def t_invalid_state():
    d = os.path.join(TMPROOT, 't_invalid')
    fix(d, 't_invalid', 'spec')
    rc = run('transition', d, 'bogus')
    if rc != 0:
        ok('Inv 1: invalid target state denied with exit 1')
    else:
        ko(f"Inv 1: rc={rc}")


# Inv 2: next returns the primary forward state.
def t_next():
    d = os.path.join(TMPROOT, 't_next')
    fix(d, 't_next', 'spec')
    rc = run('next', d)
    out = read_out()
    if rc == 0 and out == 'spec-update':
        ok('Inv 2: next from spec is spec-update')
    else:
        ko(f"next: rc={rc} out='{out}'")


# Inv 2: forward transition succeeds and writes file.
def t_forward():
    d = os.path.join(TMPROOT, 't_forward')
    fix(d, 't_forward', 'spec')
    rc = run('transition', d, 'spec-update')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'spec-update':
        ok('Inv 2: spec -> spec-update succeeds')
    else:
        ko(f"forward: rc={rc} newstate={newstate} stderr={read_err()}")


# Inv 2: skip transition denied (spec -> test-green).
def t_skip_denied():
    d = os.path.join(TMPROOT, 't_skip')
    fix(d, 't_skip', 'spec')
    rc = run('transition', d, 'test-green')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'spec':
        ok('Inv 2: spec -> test-green denied (skip)')
    else:
        ko(f"skip: rc={rc} newstate={newstate} stderr={read_err()}")


# Inv 32: full forward path works end-to-end (includes sync-deployed).
def t_full_path():
    d = os.path.join(TMPROOT, 't_full')
    fix(d, 't_full', 'spec')
    good = True
    if run('transition', d, 'spec-update') != 0:
        good = False
    if good and run('transition', d, 'test-red', '--spec-no-change-reason', 'full-path fixture') != 0:
        good = False
    for nxt in ['impl', 'sync-deployed', 'test-green', 'deprecated']:
        if good and run('transition', d, nxt) != 0:
            good = False
            break
    with open(os.path.join(d, 'feature.json')) as f:
        final = json.load(f)['tdd_state']
    if good and final == 'deprecated':
        ok('Inv 32: full forward path spec -> deprecated (through sync-deployed)')
    else:
        ko(f"full: good={good} final={final}")


# Inv 31: sync-deployed is a valid state.
def t_sync_deployed_valid():
    d = os.path.join(TMPROOT, 't_sd_valid')
    fix(d, 't_sd_valid', 'impl')
    rc = run('transition', d, 'sync-deployed')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'sync-deployed':
        ok('Inv 31: sync-deployed accepted as valid state')
    else:
        ko(f"sd valid: rc={rc} newstate={newstate} stderr={read_err()}")


# Inv 32: impl -> sync-deployed is the primary forward edge.
def t_impl_to_sync_deployed():
    d = os.path.join(TMPROOT, 't_impl_sd')
    fix(d, 't_impl_sd', 'impl')
    rc = run('next', d)
    out = read_out()
    if rc == 0 and out == 'sync-deployed':
        ok('Inv 32: next from impl is sync-deployed')
    else:
        ko(f"next impl: rc={rc} out='{out}'")


# Inv 32: sync-deployed -> test-green is the primary forward edge.
def t_sync_deployed_to_test_green():
    d = os.path.join(TMPROOT, 't_sd_tg')
    fix(d, 't_sd_tg', 'sync-deployed')
    rc = run('next', d)
    out = read_out()
    if rc == 0 and out == 'test-green':
        ok('Inv 32: next from sync-deployed is test-green')
    else:
        ko(f"next sd: rc={rc} out='{out}'")
    rc2 = run('transition', d, 'test-green')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc2 == 0 and newstate == 'test-green':
        ok('Inv 32: sync-deployed -> test-green succeeds')
    else:
        ko(f"sd->tg: rc={rc2} newstate={newstate} stderr={read_err()}")


# Inv 32: impl -> test-green is NO LONGER a primary forward edge (must go
# through sync-deployed). Denied without --force.
def t_impl_to_test_green_denied():
    d = os.path.join(TMPROOT, 't_impl_tg_denied')
    fix(d, 't_impl_tg_denied', 'impl')
    rc = run('transition', d, 'test-green')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'impl':
        ok('Inv 32: impl -> test-green denied without --force (must route through sync-deployed)')
    else:
        ko(f"impl->tg: rc={rc} newstate={newstate} (should reject)")


# Inv 2: transitions sub-command lists forward targets.
def t_transitions_cmd():
    d = os.path.join(TMPROOT, 't_trans')
    fix(d, 't_trans', 'test-green')
    rc = run('transitions', d)
    out = read_out()
    if rc == 0 and 'deprecated' in out:
        ok('Inv 2: transitions from test-green includes deprecated')
    else:
        ko(f"transitions: rc={rc} out='{out}'")


# Inv 3: test-green -> spec-update accepted without --force.
def t_alt_forward():
    d = os.path.join(TMPROOT, 't_alt')
    fix(d, 't_alt', 'test-green')
    rc = run('transition', d, 'spec-update')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'spec-update':
        ok('Inv 3: test-green -> spec-update accepted without --force')
    else:
        ko(f"alt: rc={rc} newstate={newstate} stderr={read_err()}")


# Inv 3: transitions lists spec-update among forward targets from test-green.
def t_alt_listed():
    d = os.path.join(TMPROOT, 't_alt_list')
    fix(d, 't_alt_list', 'test-green')
    rc = run('transitions', d)
    out = read_out()
    if rc == 0 and 'spec-update' in out.split():
        ok('Inv 3: transitions from test-green includes spec-update')
    else:
        ko(f"alt list: rc={rc} out='{out}'")


# Inv 4: backward transition denied without --force.
def t_backward_denied():
    d = os.path.join(TMPROOT, 't_back')
    fix(d, 't_back', 'impl')
    rc = run('transition', d, 'test-red')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'impl':
        ok('Inv 4: impl -> test-red denied without --force')
    else:
        ko(f"back: rc={rc} newstate={newstate} stderr={read_err()}")


# Inv 4: backward transition with --force succeeds.
def t_backward_forced():
    d = os.path.join(TMPROOT, 't_back_force')
    fix(d, 't_back_force', 'impl')
    rc = run('transition', d, 'test-red', '--force')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'test-red':
        ok('Inv 4: impl -> test-red allowed with --force')
    else:
        ko(f"back force: rc={rc} newstate={newstate} stderr={read_err()}")


# Inv 4: spec-update is a valid state (--force into spec-update must succeed).
def t_force_into_spec_update():
    d = os.path.join(TMPROOT, 't_force_su')
    fix(d, 't_force_su', 'spec')
    rc = run('transition', d, 'spec-update', '--force')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'spec-update':
        ok('Inv 4: --force into spec-update accepted')
    else:
        ko(f"force su: rc={rc} newstate={newstate} stderr={read_err()}")


# Inv 5: deprecated is terminal — even --force is denied.
def t_terminal():
    d = os.path.join(TMPROOT, 't_term')
    fix(d, 't_term', 'deprecated')
    rc = run('transition', d, 'spec', '--force')
    if rc != 0:
        ok('Inv 5: deprecated rejects all transitions (even with --force)')
    else:
        ko(f"term: rc={rc} - deprecated must reject all transitions")


# Side-invariant: transition updates the 'updated' field (write_state guarantee).
def t_updated_field():
    d = os.path.join(TMPROOT, 't_upd')
    fix(d, 't_upd', 'spec')
    fj = os.path.join(d, 'feature.json')
    with open(fj) as f:
        data = json.load(f)
    data['updated'] = '1999-01-01'
    with open(fj, 'w') as f:
        json.dump(data, f)
    run('transition', d, 'spec-update')
    with open(fj) as f:
        upd = json.load(f)['updated']
    if upd != '1999-01-01' and re.match(r'^\d{4}-\d{2}-\d{2}$', upd):
        ok(f"updated: 'updated' field refreshed to {upd}")
    else:
        ko(f"updated: upd={upd}")


print(f"running state-machine tests against {TDD_STEP}")
t_show(); t_invalid_state()
t_next(); t_forward(); t_skip_denied(); t_full_path(); t_transitions_cmd()
t_alt_forward(); t_alt_listed()
t_backward_denied(); t_backward_forced(); t_force_into_spec_update()
t_terminal()
t_updated_field()
t_sync_deployed_valid()
t_impl_to_sync_deployed()
t_sync_deployed_to_test_green()
t_impl_to_test_green_denied()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
