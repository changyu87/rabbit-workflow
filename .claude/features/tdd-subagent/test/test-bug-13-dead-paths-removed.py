#!/usr/bin/env python3
# test-bug-13-dead-paths-removed.py
#
# TDD-SUBAGENT-BACKLOG-13: regression tests asserting that the legacy local
# backlog directory scan path (.claude/backlogs/<feature>/<ID>/item.json) is
# removed from tdd-step.py. Discovery of in-progress backlog items is now the
# dispatcher's responsibility (via --linked-item / --linked-items in
# dispatch-tdd-subagent.py). tdd-step.py's auto_close_backlog must NOT scan a
# local backlog directory.
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')

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


def _read():
    with open(TDD_STEP) as f:
        return f.read()


# t1: tdd-step.py source no longer references the legacy local backlog dir
# path '.claude/backlogs/'. Doc comments may still describe legacy behaviour,
# so only fail when the code body (outside the auto_close_backlog docstring
# explanation) references it as a path.
def t1_no_local_backlog_path():
    src = _read()
    m = re.search(
        r"def auto_close_backlog\(.*?\):\s*\n(.*?)(?=\n(?:def|class)\s)",
        src, re.DOTALL,
    )
    if not m:
        ko("t1: auto_close_backlog function not found")
        return
    body = m.group(1)
    # The body must NOT construct a '.claude/backlogs/' path. Both string
    # literal and os.path.join('.claude', 'backlogs', ...) patterns count.
    has_str_literal = '.claude/backlogs' in body
    has_join_pattern = bool(re.search(r"['\"]backlogs['\"]", body))
    if not has_str_literal and not has_join_pattern:
        ok("t1: auto_close_backlog body does not construct .claude/backlogs/ path")
    else:
        ko(
            "t1: auto_close_backlog body still references legacy local backlog path "
            f"(str_literal={has_str_literal} join_pattern={has_join_pattern})"
        )


# t2: _head_sha helper is removed (its only caller was the legacy scan loop).
def t2_head_sha_helper_removed():
    src = _read()
    if 'def _head_sha' in src:
        ko("t2: _head_sha helper still defined (only caller was the removed legacy scan)")
    else:
        ok("t2: _head_sha helper removed")


# t3: auto_close_backlog is still defined (called by _post_test_green_hooks)
# and remains a true no-op or guarded best-effort: it must not raise and must
# not iterate any local directory.
def t3_auto_close_backlog_present_and_safe():
    src = _read()
    if 'def auto_close_backlog' not in src:
        ko("t3: auto_close_backlog function removed (still called by _post_test_green_hooks)")
        return
    m = re.search(
        r"def auto_close_backlog\(.*?\):\s*\n(.*?)(?=\n(?:def|class)\s)",
        src, re.DOTALL,
    )
    body = m.group(1) if m else ''
    # No directory iteration via os.listdir on a backlog path.
    if 'os.listdir' in body and 'backlog' in body:
        ko("t3: auto_close_backlog still iterates a backlog directory")
    else:
        ok("t3: auto_close_backlog present and contains no backlog-dir iteration")


print(f"running BACKLOG-13 dead-paths regression tests against {TDD_STEP}")
t1_no_local_backlog_path()
t2_head_sha_helper_removed()
t3_auto_close_backlog_present_and_safe()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
