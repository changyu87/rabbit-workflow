#!/usr/bin/env python3
# Regression test for TDD-SUBAGENT-BUG-52.
#
# The _run_enforcement_checks() helper in tdd-step.py previously invoked
# check-template-schema-producer-consistency.py with an empty args list,
# which made the script short-circuit at argparse (missing positional
# <template-path>) and emit a warning every test-green cycle. The fix
# passes the canonical bug-template path so the check actually runs.
#
# This test asserts, on both canonical copies of tdd-step.py (the feature
# copy and the agent copy), that:
#   1. The args list passed to check-template-schema-producer-consistency.py
#      is non-empty.
#   2. It references the bug-template.json path under the contract feature's
#      templates directory.
import os
import re
import sys

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')
)

TARGETS = [
    os.path.join(REPO_ROOT, '.claude', 'features', 'tdd-subagent',
                 'scripts', 'tdd-step.py'),
    os.path.join(REPO_ROOT, '.claude', 'agents', 'tdd-subagent',
                 'scripts', 'tdd-step.py'),
]

# Match the _run("check-template-schema-producer-consistency.py", <args>, ...)
# call and capture the args expression so we can assert on its shape.
CALL_RE = re.compile(
    r"_run\(\s*[\"']check-template-schema-producer-consistency\.py[\"']\s*,"
    r"\s*(\[[^\]]*\])\s*,",
)

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def check(path):
    if not os.path.isfile(path):
        ko(f"missing: {path}")
        return
    with open(path) as fh:
        src = fh.read()
    m = CALL_RE.search(src)
    if not m:
        ko(f"no _run(check-template-schema-producer-consistency.py, ...) call in {path}")
        return
    args_expr = m.group(1).strip()
    if args_expr == '[]':
        ko(f"args list is empty (BUG-52 regression) in {path}: {args_expr}")
        return
    ok(f"args list non-empty in {path}: {args_expr}")
    if 'bug-template.json' not in args_expr:
        ko(f"args list does not reference bug-template.json in {path}: {args_expr}")
        return
    ok(f"args list references bug-template.json in {path}")


for t in TARGETS:
    check(t)

print(f"\n{PASS} pass, {FAIL} fail")
sys.exit(0 if FAIL == 0 else 1)
