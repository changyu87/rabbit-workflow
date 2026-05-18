#!/usr/bin/env python3
# E2E test for the five Wave-1 critical dispatch-tdd-subagent.py prompt fixes:
#
#   BUG-15 (Inv 8 updated): close calls use rabbit-file/scripts/item-status.py;
#       legacy bug-status.py and backlog-item-status.py references are banned.
#   BUG-18 (Inv 23): STEP 3 LOCK must NOT use `trap '... rm -f ...' EXIT`.
#       STEP 9 UNLOCK must do explicit `rm -f .rabbit-scope-active-<feature>`.
#   BUG-22 (Inv 24): STEP 7 CODE-REVIEW must invoke
#       Skill("superpowers:requesting-code-review") (not "superpowers:code-reviewer").
#   BUG-28 (Inv 25): STEP 6 IMPLEMENT loop must have `git add` + `git commit`
#       INSIDE the loop, BEFORE the `tdd-step.py transition ... impl` call.
#   BUG-29 (Inv 26): STEP 8 TEST-GREEN must capture impl SHA (git rev-parse HEAD)
#       BEFORE STEP 9's chore commit; tdd-report fully written before UNLOCK chore.

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


def _run_dispatch(extra_args=None):
    args = [
        sys.executable, DISPATCH_PY,
        '--scope', 'tdd-subagent',
        '--spec', SPEC_PATH,
        '--human-approval-gate', 'false',
    ]
    if extra_args:
        args.extend(extra_args)
    res = subprocess.run(args, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        ko(f"dispatch-tdd-subagent.py returned {res.returncode}: {res.stderr}")
        return ""
    return res.stdout


def _section(prompt, step_no, step_name):
    pattern = (
        rf"STEP\s+{step_no}\s+[-—]\s+{step_name}\s*\n[═=]+\s*\n"
        r"(.*?)(?=\n[═=]{5,}\s*\n|\Z)"
    )
    m = re.search(pattern, prompt, re.DOTALL)
    return m.group(1) if m else ""


def _strip_spec_embed(prompt):
    """Strip the embedded SPEC and Implementation Suggestion blocks from the
    prompt so that BUG-15/BUG-22 checks only inspect operational instructions
    authored by dispatch-tdd-subagent.py — not the spec text that may
    legitimately mention banned identifiers (e.g., "bug-status.py no longer
    exists")."""
    # Spec block is bounded by the "SPEC" heading and the next "═════" heading.
    out = re.sub(
        r"═+\s*\nSPEC\s*\n═+\s*\n.*?(?=\n═{5,}\s*\n)",
        "═══\nSPEC\n═══\n[stripped]\n",
        prompt, count=1, flags=re.DOTALL,
    )
    return out


# ---- BUG-15: close calls use item-status.py, not legacy scripts ----------

def t_bug15_uses_item_status_py_with_linked_item():
    prompt = _strip_spec_embed(_run_dispatch([
        '--linked-item', 'rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-99',
        '--item-type', 'bug',
    ]))
    if not prompt:
        return
    if 'item-status.py' in prompt:
        ok("bug15: prompt references item-status.py")
    else:
        ko("bug15: prompt does NOT reference item-status.py")
    if 'bug-status.py' not in prompt:
        ok("bug15: prompt does NOT reference bug-status.py")
    else:
        ko("bug15: prompt still references bug-status.py")
    if 'backlog-item-status.py' not in prompt:
        ok("bug15: prompt does NOT reference backlog-item-status.py")
    else:
        ko("bug15: prompt still references backlog-item-status.py")


def t_bug15_backlog_item_also_uses_item_status_py():
    prompt = _strip_spec_embed(_run_dispatch([
        '--linked-item', 'rabbit/features/tdd-subagent/backlog/SOMEID',
        '--item-type', 'backlog',
    ]))
    if not prompt:
        return
    if 'item-status.py' in prompt and 'backlog-item-status.py' not in prompt:
        ok("bug15: backlog mode uses item-status.py, not backlog-item-status.py")
    else:
        ko("bug15: backlog mode still references legacy backlog-item-status.py")


# ---- BUG-18: no trap in LOCK; explicit rm -f in UNLOCK -------------------

def t_bug18_lock_has_no_trap():
    prompt = _run_dispatch()
    if not prompt:
        return
    lock = _section(prompt, 3, 'LOCK')
    if not lock:
        ko("bug18: STEP 3 — LOCK section not found")
        return
    # Operative trap command form: `trap '...' EXIT` (with quoted body + signal).
    # Prose mentions of the word "trap" in an explanation paragraph are OK.
    if re.search(r"^\s*trap\s+['\"].*['\"]\s+EXIT\b", lock, re.MULTILINE):
        ko("bug18: STEP 3 LOCK still contains an operative `trap ... EXIT` command")
    else:
        ok("bug18: STEP 3 LOCK has no operative `trap ... EXIT` command")


def t_bug18_unlock_has_explicit_rm_f():
    prompt = _run_dispatch()
    if not prompt:
        return
    unlock = _section(prompt, 9, 'UNLOCK')
    if not unlock:
        ko("bug18: STEP 9 — UNLOCK section not found")
        return
    marker = '.rabbit-scope-active-tdd-subagent'
    if re.search(rf"rm\s+-f\s+\S*{re.escape(marker)}", unlock):
        ok("bug18: STEP 9 UNLOCK has explicit `rm -f` of scope marker")
    else:
        ko("bug18: STEP 9 UNLOCK lacks explicit `rm -f` of scope marker")


def t_bug18_lock_has_explanatory_note():
    prompt = _run_dispatch()
    if not prompt:
        return
    lock = _section(prompt, 3, 'LOCK')
    if not lock:
        ko("bug18: STEP 3 LOCK section not found")
        return
    # Look for an explanation referencing per-call/separate/new shell process semantics.
    if re.search(
        r"(per[- ]call|separate|each).*(shell|Bash|process)",
        lock, re.IGNORECASE | re.DOTALL,
    ):
        ok("bug18: STEP 3 LOCK includes explanation about per-call shell process")
    else:
        ko("bug18: STEP 3 LOCK missing explanation about per-call shell process")


# ---- BUG-22: CODE-REVIEW uses superpowers:requesting-code-review ---------

def t_bug22_uses_correct_review_skill():
    prompt = _strip_spec_embed(_run_dispatch())
    if not prompt:
        return
    if 'Skill("superpowers:requesting-code-review")' in prompt:
        ok("bug22: prompt uses Skill(\"superpowers:requesting-code-review\")")
    else:
        ko("bug22: prompt does NOT use the correct review skill name")
    if 'Skill("superpowers:code-reviewer")' not in prompt:
        ok("bug22: prompt does NOT use bogus Skill(\"superpowers:code-reviewer\")")
    else:
        ko("bug22: prompt still uses bogus Skill(\"superpowers:code-reviewer\")")


# ---- BUG-28: IMPLEMENT loop commits impl files BEFORE impl transition ----

def t_bug28_implement_loop_has_git_add_and_commit():
    prompt = _run_dispatch()
    if not prompt:
        return
    impl = _section(prompt, 6, 'IMPLEMENT')
    if not impl:
        ko("bug28: STEP 6 — IMPLEMENT section not found")
        return
    if re.search(r"git\s+add\b", impl):
        ok("bug28: STEP 6 IMPLEMENT contains `git add` instruction")
    else:
        ko("bug28: STEP 6 IMPLEMENT missing `git add` instruction")
    if re.search(r"git\s+commit\b", impl):
        ok("bug28: STEP 6 IMPLEMENT contains `git commit` instruction")
    else:
        ko("bug28: STEP 6 IMPLEMENT missing `git commit` instruction")


def t_bug28_commit_before_impl_transition():
    prompt = _run_dispatch()
    if not prompt:
        return
    impl = _section(prompt, 6, 'IMPLEMENT')
    if not impl:
        ko("bug28: STEP 6 section not found")
        return
    m_commit = re.search(r"git\s+commit\b", impl)
    m_trans = re.search(r"tdd-step\.py\s+transition\s+\S+\s+impl\b", impl)
    if not m_commit:
        ko("bug28: no git commit instruction in STEP 6")
        return
    if not m_trans:
        ko("bug28: no tdd-step.py transition ... impl instruction in STEP 6")
        return
    if m_commit.start() < m_trans.start():
        ok("bug28: `git commit` appears BEFORE `tdd-step.py transition ... impl`")
    else:
        ko("bug28: `git commit` appears AFTER `tdd-step.py transition ... impl`")


# ---- BUG-29: STEP 8 captures impl SHA BEFORE STEP 9 chore commit ---------

def t_bug29_step8_captures_impl_sha_before_chore_commit():
    prompt = _run_dispatch()
    if not prompt:
        return
    # Find STEP 8 region and STEP 9 region.
    m_step8 = re.search(r"STEP\s+8\s+[-—]\s+TEST-GREEN\s*\n[═=]+\s*\n", prompt)
    m_step9 = re.search(r"STEP\s+9\s+[-—]\s+UNLOCK\s*\n[═=]+\s*\n", prompt)
    if not m_step8 or not m_step9:
        ko("bug29: STEP 8 or STEP 9 header not found")
        return
    step8_body = prompt[m_step8.end():m_step9.start()]
    # Inside STEP 8 (before STEP 9), must have a `git rev-parse HEAD` capture
    # for the impl SHA — bound to a variable, not a literal placeholder.
    if re.search(r"IMPL_SHA\s*=\s*\$?\(?\s*git\s+rev-parse\s+HEAD", step8_body):
        ok("bug29: STEP 8 captures IMPL_SHA via `git rev-parse HEAD`")
    else:
        ko("bug29: STEP 8 lacks IMPL_SHA capture before STEP 9")
    # Must mention ordering — that the capture happens BEFORE the chore commit.
    if re.search(
        r"(BEFORE|before).*(chore|STEP\s+9|UNLOCK|advance|capture)",
        step8_body, re.DOTALL,
    ):
        ok("bug29: STEP 8 documents capture-before-chore-commit ordering")
    else:
        ko("bug29: STEP 8 missing ordering note about capture before chore commit")


def t_bug29_tdd_report_impl_commit_uses_captured_sha():
    prompt = _run_dispatch()
    if not prompt:
        return
    m_step8 = re.search(r"STEP\s+8\s+[-—]\s+TEST-GREEN\s*\n[═=]+\s*\n", prompt)
    m_step9 = re.search(r"STEP\s+9\s+[-—]\s+UNLOCK\s*\n[═=]+\s*\n", prompt)
    if not m_step8 or not m_step9:
        ko("bug29: STEP 8 or STEP 9 header not found")
        return
    step8_body = prompt[m_step8.end():m_step9.start()]
    # The tdd-report's impl_commit field should reference the captured SHA.
    if re.search(r'"impl_commit"\s*:\s*"?\$?IMPL_SHA', step8_body) or \
       re.search(r'"impl_commit"\s*:\s*"<IMPL_SHA', step8_body):
        ok("bug29: tdd-report `impl_commit` references captured IMPL_SHA")
    else:
        ko("bug29: tdd-report `impl_commit` does not reference captured IMPL_SHA")


# ---- Run -------------------------------------------------------------------

print("running tdd-subagent five-prompt-fixes tests (BUG-15, 18, 22, 28, 29)")
t_bug15_uses_item_status_py_with_linked_item()
t_bug15_backlog_item_also_uses_item_status_py()
t_bug18_lock_has_no_trap()
t_bug18_unlock_has_explicit_rm_f()
t_bug18_lock_has_explanatory_note()
t_bug22_uses_correct_review_skill()
t_bug28_implement_loop_has_git_add_and_commit()
t_bug28_commit_before_impl_transition()
t_bug29_step8_captures_impl_sha_before_chore_commit()
t_bug29_tdd_report_impl_commit_uses_captured_sha()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
