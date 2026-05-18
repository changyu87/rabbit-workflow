#!/usr/bin/env python3
# E2E test for tdd-subagent spec invariant 31 (BUG-19):
#
#   31. The assembled TDD subagent prompt MUST handle the case where the
#       starting tdd_state (in feature.json) is test-green from a prior
#       completed cycle. The state machine is forward-only and the only
#       valid forward transition from test-green is to spec-update. The
#       prompt MUST therefore include an explicit
#       `tdd-step.py transition <feature_dir> spec-update` BEFORE the
#       STEP 5 `test-red` transition.
#
# Asserts against the prompt produced by dispatch-tdd-subagent.py.

import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

DISPATCH_PY = os.path.join(
    REPO_ROOT,
    '.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py',
)
SPEC_PATH = os.path.join(
    REPO_ROOT, '.claude/features/tdd-subagent/docs/spec/spec.md'
)

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


def _run_dispatch():
    args = [
        sys.executable, DISPATCH_PY,
        '--scope', 'tdd-subagent',
        '--spec', SPEC_PATH,
        '--human-approval-gate', 'false',
    ]
    res = subprocess.run(args, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        ko(f"dispatch-tdd-subagent.py returned {res.returncode}: {res.stderr}")
        return ""
    return res.stdout


def t_inv31_prompt_includes_spec_update_transition():
    prompt = _run_dispatch()
    if not prompt:
        return
    # The prompt MUST mention a `tdd-step.py transition ... spec-update` call.
    if re.search(r"tdd-step\.py\s+transition\s+\S+\s+spec-update", prompt):
        ok("inv31: prompt includes a 'tdd-step.py transition <dir> spec-update' call")
    else:
        ko("inv31: prompt does NOT include any 'tdd-step.py transition <dir> spec-update' call")


def t_inv31_spec_update_before_test_red():
    prompt = _run_dispatch()
    if not prompt:
        return
    m_spec = re.search(r"tdd-step\.py\s+transition\s+\S+\s+spec-update", prompt)
    m_red = re.search(r"tdd-step\.py\s+transition\s+\S+\s+test-red", prompt)
    if not m_red:
        ko("inv31: prompt is missing the 'transition <dir> test-red' call")
        return
    if not m_spec:
        ko("inv31: prompt is missing the 'transition <dir> spec-update' call")
        return
    if m_spec.start() < m_red.start():
        ok("inv31: spec-update transition appears BEFORE test-red transition")
    else:
        ko(
            "inv31: spec-update transition appears AFTER test-red transition "
            f"(spec-update@{m_spec.start()}, test-red@{m_red.start()})"
        )


# ---- Run -------------------------------------------------------------------

print("running tdd-subagent spec-update-before-test-red tests (inv 31, BUG-19)")
t_inv31_prompt_includes_spec_update_transition()
t_inv31_spec_update_before_test_red()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
