#!/usr/bin/env python3
# E2E test for tdd-subagent spec invariant 27 (BUG-31):
#
#   27. The assembled prompt's STEP 1 SPEC-READ MUST diff the spec against
#       the PARENT commit, not against HEAD. Use
#       `git diff HEAD~1 -- <feature_dir>/docs/spec/`. Using `git diff HEAD`
#       is always empty because rabbit-feature-touch Step 3 commits the spec
#       BEFORE dispatching the subagent (Inv 16); the working tree is clean
#       at subagent start.
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


def _spec_read_section(prompt):
    # STEP 1 — SPEC-READ section extends until the next "═══" block heading.
    m = re.search(
        r"STEP\s+1\s+[-—]\s+SPEC-READ\s*\n[═=]+\s*\n(.*?)(?=\n[═=]{5,}\s*\n|\Z)",
        prompt, re.DOTALL,
    )
    return m.group(1) if m else ""


def t_inv27_spec_read_uses_head_tilde_1():
    prompt = _run_dispatch()
    if not prompt:
        return
    spec_read = _spec_read_section(prompt)
    if not spec_read:
        ko("inv27: STEP 1 — SPEC-READ section not found in dispatch prompt")
        return
    if "git diff HEAD~1 --" not in spec_read:
        ko("inv27: SPEC-READ does not contain 'git diff HEAD~1 --'")
    else:
        ok("inv27: SPEC-READ uses 'git diff HEAD~1 --'")


def t_inv27_spec_read_does_not_use_bare_head():
    prompt = _run_dispatch()
    if not prompt:
        return
    spec_read = _spec_read_section(prompt)
    if not spec_read:
        ko("inv27: STEP 1 — SPEC-READ section not found in dispatch prompt")
        return
    # Must NOT contain the bare 'git diff HEAD --' form (without ~1).
    # Use a regex that matches HEAD followed by something other than '~'.
    if re.search(r"git\s+diff\s+HEAD\s+--", spec_read):
        ko("inv27: SPEC-READ still contains bare 'git diff HEAD --' (without ~1)")
    else:
        ok("inv27: SPEC-READ does not contain bare 'git diff HEAD --'")


# ---- Run -------------------------------------------------------------------

print("running tdd-subagent spec-read HEAD~1 tests (inv 27, BUG-31)")
t_inv27_spec_read_uses_head_tilde_1()
t_inv27_spec_read_does_not_use_bare_head()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
