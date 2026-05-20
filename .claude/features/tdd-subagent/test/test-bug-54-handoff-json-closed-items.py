#!/usr/bin/env python3
# Tests for TDD-SUBAGENT-BUG-54: HANDOFF_JSON.closed_items must reflect actual
# closures (primary --linked-item + every --linked-items entry), not the
# hard-coded empty array. Per Inv 19 the JSON HANDOFF is the machine-first
# source of truth; if `closed_items` is always `[]`, downstream parsers see
# no closures even when items were actually closed by the cycle.
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
SCRIPTS_DIR = os.path.join(FEATURE_DIR, 'scripts')
DISPATCH = os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py')
TMPROOT = tempfile.mkdtemp()

FIND_FEATURE_PY = os.path.join(
    os.path.abspath(os.path.join(SCRIPT_DIR, '../..')),
    'contract', 'scripts', 'find-feature.py'
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


def make_rabbit_root(root):
    os.makedirs(os.path.join(root, '.claude/features/tdd-subagent/docs/spec'), exist_ok=True)
    os.makedirs(os.path.join(root, '.claude/features/contract/scripts'), exist_ok=True)
    shutil.copy(FIND_FEATURE_PY, os.path.join(root, '.claude/features/contract/scripts/find-feature.py'))
    os.chmod(os.path.join(root, '.claude/features/contract/scripts/find-feature.py'), 0o755)
    feature_json = {
        "name": "tdd-subagent",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "fixture feature",
    }
    with open(os.path.join(root, '.claude/features/tdd-subagent/feature.json'), 'w') as f:
        json.dump(feature_json, f)
    with open(os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md'), 'w') as f:
        f.write('# Spec\nMinimal spec content.')


def run_dispatch(root, extra_args):
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    return subprocess.run(
        ['python3', DISPATCH, '--scope', 'tdd-subagent', '--spec', spec] + extra_args,
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )


def extract_handoff_json_block(prompt):
    """Extract the fenced JSON block following the HANDOFF_JSON: marker.

    Returns the raw JSON text inside the ```json ... ``` fence, or None if
    the block is not present / malformed.
    """
    m = re.search(r'HANDOFF_JSON:\s*```json\s*(\{.*?\})\s*```', prompt, re.DOTALL)
    if not m:
        return None
    return m.group(1)


# t1: primary --linked-item alone -> HANDOFF_JSON.closed_items includes it
def t1_primary_only():
    root = os.path.join(TMPROOT, 't1_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-item', 'rabbit/features/tdd-subagent/bugs/TDD-SUBAGENT-BUG-54',
        '--item-type', 'bug',
    ])
    if r.returncode != 0:
        ko(f"t1: dispatch rc={r.returncode}, stderr={r.stderr}")
        return
    block = extract_handoff_json_block(r.stdout)
    if block is None:
        ko("t1: HANDOFF_JSON fenced json block missing")
        return
    # The JSON template uses <pass|fail> placeholders that are not valid JSON;
    # we only assert textual presence of the primary item id inside the
    # closed_items value, not full json.loads parseability.
    closed_match = re.search(r'"closed_items"\s*:\s*\[([^\]]*)\]', block, re.DOTALL)
    if not closed_match:
        ko("t1: HANDOFF_JSON missing 'closed_items' field")
        return
    closed_body = closed_match.group(1)
    if 'TDD-SUBAGENT-BUG-54' not in closed_body:
        ko(f"t1: HANDOFF_JSON closed_items does not list primary item; got: {closed_body!r}")
        return
    ok("t1: HANDOFF_JSON closed_items includes primary --linked-item")


# t2: primary + secondaries -> HANDOFF_JSON.closed_items lists ALL of them
def t2_primary_plus_secondaries():
    root = os.path.join(TMPROOT, 't2_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-item', 'rabbit/features/tdd-subagent/bugs/TDD-SUBAGENT-BUG-54',
        '--item-type', 'bug',
        '--linked-items', 'rabbit-cage:bug:RABBIT-CAGE-BUG-9,rabbit-file:backlog:RF-BL-3',
    ])
    if r.returncode != 0:
        ko(f"t2: dispatch rc={r.returncode}, stderr={r.stderr}")
        return
    block = extract_handoff_json_block(r.stdout)
    if block is None:
        ko("t2: HANDOFF_JSON fenced json block missing")
        return
    closed_match = re.search(r'"closed_items"\s*:\s*\[([^\]]*)\]', block, re.DOTALL)
    if not closed_match:
        ko("t2: HANDOFF_JSON missing 'closed_items' field")
        return
    closed_body = closed_match.group(1)
    missing = [s for s in (
        'TDD-SUBAGENT-BUG-54',
        'RABBIT-CAGE-BUG-9',
        'RF-BL-3',
    ) if s not in closed_body]
    if missing:
        ko(f"t2: HANDOFF_JSON closed_items missing entries: {missing}; got: {closed_body!r}")
        return
    ok("t2: HANDOFF_JSON closed_items lists primary + all secondaries")


# t3: no linked items at all -> HANDOFF_JSON.closed_items is empty array []
def t3_no_items():
    root = os.path.join(TMPROOT, 't3_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [])
    if r.returncode != 0:
        ko(f"t3: dispatch rc={r.returncode}, stderr={r.stderr}")
        return
    block = extract_handoff_json_block(r.stdout)
    if block is None:
        ko("t3: HANDOFF_JSON fenced json block missing")
        return
    closed_match = re.search(r'"closed_items"\s*:\s*\[([^\]]*)\]', block, re.DOTALL)
    if not closed_match:
        ko("t3: HANDOFF_JSON missing 'closed_items' field")
        return
    closed_body = closed_match.group(1).strip()
    if closed_body == "":
        ok("t3: HANDOFF_JSON closed_items is empty array when no items provided")
    else:
        ko(f"t3: HANDOFF_JSON closed_items should be empty; got: {closed_body!r}")


def main():
    print("=== test-bug-54-handoff-json-closed-items ===")
    t1_primary_only()
    t2_primary_plus_secondaries()
    t3_no_items()
    print(f"PASS={PASS} FAIL={FAIL}")
    shutil.rmtree(TMPROOT, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
