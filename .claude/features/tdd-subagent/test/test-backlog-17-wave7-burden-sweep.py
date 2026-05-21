#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BACKLOG-17 (wave 7 historical-burden sweep).
#
# Pins the active-form prose introduced by the sweep and ensures the removed
# tombstone clauses do not reappear in spec.md, contract.md, the dispatch
# script's authored output, or its inline comments / help text.
#
# Spec-level removals (positive-form assertions preserved):
#   - Inv 3: "legacy bug-status.py" / "backlog-item-status.py" clause gone
#   - Inv 7: "legacy --no-human-approval flag" clause gone
#   - Inv 18: "legacy nested form is retired" clause gone
#   - Inv 19: "legacy YAML-like HANDOFF block (for ... backward-compatible
#             dispatchers)" reframed to "YAML-style HANDOFF block (the
#             human-readable view)"
#   - contract.md provides.scripts.dispatch.stdin: "Legacy bug-dispatch and
#     backlog-dispatch positional flags have been removed" clause gone
#
# Dispatch-script reframings:
#   - argparse --human-approval-gate help drops the "legacy --no-human-approval"
#     parenthetical
#   - inline comment "legacy YAML block above" → "human-readable YAML block above"
#   - HANDOFF_JSON preamble comment "remains for human readability and
#     backward-compatible parsers" → "human-readable view alongside the
#     machine-first JSON"
#
# Test-docstring reframing:
#   - test-dispatch-linked-items.py t6 docstring no longer says "backward compat"

import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

FEATURE_DIR = os.path.join(REPO_ROOT, '.claude', 'features', 'tdd-subagent')
SPEC_MD = os.path.join(FEATURE_DIR, 'docs', 'spec', 'spec.md')
CONTRACT_MD = os.path.join(FEATURE_DIR, 'docs', 'spec', 'contract.md')
DISPATCH_PY = os.path.join(FEATURE_DIR, 'scripts', 'dispatch-tdd-subagent.py')
LINKED_ITEMS_TEST = os.path.join(
    FEATURE_DIR, 'test', 'test-dispatch-linked-items.py'
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


def _read(path):
    with open(path) as f:
        return f.read()


# ---- Spec / contract tombstone removal ------------------------------------

def t_spec_no_legacy_bug_status_clause():
    spec = _read(SPEC_MD)
    if 'legacy' in spec.lower() and 'bug-status.py' in spec:
        ko("spec.md still mentions legacy bug-status.py")
        return
    # Positive form: item-status.py reference preserved.
    if 'item-status.py' in spec:
        ok("spec.md keeps positive item-status.py reference, drops legacy bug-status tombstone")
    else:
        ko("spec.md lost positive item-status.py reference")


def t_spec_no_legacy_no_human_approval_clause():
    spec = _read(SPEC_MD)
    if '--no-human-approval' in spec:
        ko("spec.md still mentions legacy --no-human-approval flag")
        return
    if '--human-approval-gate' in spec:
        ok("spec.md keeps positive --human-approval-gate, drops --no-human-approval tombstone")
    else:
        ko("spec.md lost positive --human-approval-gate reference")


def t_spec_no_legacy_nested_form_clause():
    spec = _read(SPEC_MD)
    if re.search(r'legacy\s+nested\s+form', spec, re.IGNORECASE):
        ko("spec.md still mentions 'legacy nested form' (Inv 18)")
        return
    if 'flat shape' in spec:
        ok("spec.md keeps positive 'flat shape' assertion (Inv 18)")
    else:
        ko("spec.md lost positive 'flat shape' assertion")


def t_spec_inv19_reframed_to_human_readable_view():
    spec = _read(SPEC_MD)
    if 'backward-compatible' in spec.lower() or 'backward compat' in spec.lower():
        ko("spec.md still contains backward-compat phrasing")
        return
    if 'human-readable view' in spec:
        ok("spec.md Inv 19 reframed to 'human-readable view'")
    else:
        ko("spec.md Inv 19 missing 'human-readable view' phrasing")


def t_contract_no_legacy_positional_flags_clause():
    contract = _read(CONTRACT_MD)
    if 'Legacy bug-dispatch' in contract or 'backlog-dispatch positional' in contract:
        ko("contract.md still mentions Legacy bug-dispatch / backlog-dispatch positional flags")
        return
    # Positive form: --linked-item / --linked-items still listed in stdin.
    if '--linked-item' in contract and '--linked-items' in contract:
        ok("contract.md keeps --linked-item / --linked-items, drops legacy positional tombstone")
    else:
        ko("contract.md lost --linked-item / --linked-items references")


# ---- Dispatch script reframings -------------------------------------------

def t_dispatch_argparse_help_no_legacy_flag_mention():
    src = _read(DISPATCH_PY)
    # Locate the --human-approval-gate help string region by finding the
    # argument anchor and walking to the closing `)` while tracking depth.
    anchor = src.find('"--human-approval-gate"')
    if anchor < 0:
        ko("dispatch: --human-approval-gate argparse anchor not found")
        return
    # Walk back to the matching add_argument( opening.
    open_idx = src.rfind('add_argument(', 0, anchor)
    if open_idx < 0:
        ko("dispatch: enclosing add_argument( not found")
        return
    depth = 0
    end = None
    for i in range(open_idx, len(src)):
        c = src[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        ko("dispatch: could not find closing paren of add_argument block")
        return
    block = src[open_idx:end]
    if 'legacy' in block.lower() or '--no-human-approval' in block:
        ko("dispatch: --human-approval-gate help still mentions legacy flag")
    else:
        ok("dispatch: --human-approval-gate help no longer mentions legacy flag")


def t_dispatch_inline_comment_reframes_closed_items_yaml():
    src = _read(DISPATCH_PY)
    if 'legacy YAML block above' in src:
        ko("dispatch: comment still says 'legacy YAML block above'")
    elif 'human-readable YAML block above' in src:
        ok("dispatch: comment reframed to 'human-readable YAML block above'")
    else:
        ko("dispatch: comment does not reference YAML block (expected reframed phrase)")


def t_dispatch_handoff_json_preamble_reframed():
    src = _read(DISPATCH_PY)
    if 'backward-compatible parsers' in src:
        ko("dispatch: HANDOFF_JSON preamble still says 'backward-compatible parsers'")
        return
    if 'human-readable view alongside the machine-first JSON' in src:
        ok("dispatch: HANDOFF_JSON preamble reframed to human-readable view")
    else:
        ko("dispatch: HANDOFF_JSON preamble missing expected reframed phrase")


# ---- Test-docstring reframing ---------------------------------------------

def t_linked_items_t6_no_backward_compat_framing():
    src = _read(LINKED_ITEMS_TEST)
    # Locate the t6 function definition.
    m = re.search(r'def\s+t6\s*\(\s*\)\s*:.*?(?=\n#\s|\ndef\s|\Z)', src, re.DOTALL)
    if not m:
        ko("linked-items test: t6 function not found")
        return
    t6_region = src[:m.end()]
    # The reframing target is the comment line ABOVE def t6 plus any string
    # literals INSIDE t6 that mention "backward compat".
    # Take the 6 lines preceding `def t6`:
    lines = src.splitlines()
    t6_idx = next((i for i, line in enumerate(lines) if re.match(r'^def\s+t6\s*\(', line)), None)
    if t6_idx is None:
        ko("linked-items test: could not locate def t6 line")
        return
    preceding = "\n".join(lines[max(0, t6_idx - 4): t6_idx])
    func_body_end = t6_idx + 1
    while func_body_end < len(lines) and (
        lines[func_body_end].startswith(' ') or lines[func_body_end].strip() == ''
    ):
        func_body_end += 1
    body = "\n".join(lines[t6_idx: func_body_end])
    region = preceding + "\n" + body
    if re.search(r'backward[- ]compat', region, re.IGNORECASE):
        ko("linked-items test t6: still framed as backward-compat")
    else:
        ok("linked-items test t6: no longer framed as backward-compat")


# ---- Run -------------------------------------------------------------------

print("running tdd-subagent BACKLOG-17 wave 7 burden-sweep tests")
t_spec_no_legacy_bug_status_clause()
t_spec_no_legacy_no_human_approval_clause()
t_spec_no_legacy_nested_form_clause()
t_spec_inv19_reframed_to_human_readable_view()
t_contract_no_legacy_positional_flags_clause()
t_dispatch_argparse_help_no_legacy_flag_mention()
t_dispatch_inline_comment_reframes_closed_items_yaml()
t_dispatch_handoff_json_preamble_reframed()
t_linked_items_t6_no_backward_compat_framing()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
