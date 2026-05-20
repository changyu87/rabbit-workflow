#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BACKLOG-15 LOW F4.
#
# dispatch-tdd-subagent.py's _close_call plumbing was simplified — the prior
# implementation had _derive_feature_and_id + _close_call + three parallel
# accumulator lists. The simplified path builds a single list of role-tagged
# dicts and renders via one template.
#
# Contract for the refactor: the assembled prompt's UNLOCK close-call block
# MUST be byte-identical across primary-only, primary+secondary, and
# secondary-only invocations. This test pins the byte-exact output of the
# STEP 9 UNLOCK block for the primary+two-secondary case so any future
# accidental drift fails fast.
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DISPATCH = os.path.join(
    REPO_ROOT, ".claude", "features", "tdd-subagent",
    "scripts", "dispatch-tdd-subagent.py",
)
FIND_FEATURE = os.path.join(
    REPO_ROOT, ".claude", "features", "contract",
    "scripts", "find-feature.py",
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


def make_root(tmp):
    os.makedirs(os.path.join(tmp, ".claude/features/tdd-subagent/docs/spec"), exist_ok=True)
    os.makedirs(os.path.join(tmp, ".claude/features/contract/scripts"), exist_ok=True)
    shutil.copy(FIND_FEATURE, os.path.join(tmp, ".claude/features/contract/scripts/find-feature.py"))
    os.chmod(os.path.join(tmp, ".claude/features/contract/scripts/find-feature.py"), 0o755)
    with open(os.path.join(tmp, ".claude/features/tdd-subagent/feature.json"), "w") as f:
        json.dump({
            "name": "tdd-subagent", "version": "1.0.0", "owner": "t",
            "tdd_state": "test-green", "summary": "f",
        }, f)
    with open(os.path.join(tmp, ".claude/features/tdd-subagent/docs/spec/spec.md"), "w") as f:
        f.write("# spec\n")


def dispatch(root, extra):
    spec = os.path.join(root, ".claude/features/tdd-subagent/docs/spec/spec.md")
    return subprocess.run(
        [sys.executable, DISPATCH, "--scope", "tdd-subagent", "--spec", spec] + extra,
        capture_output=True, text=True,
        env={**os.environ, "RABBIT_ROOT": root},
    )


def slice_unlock(stdout):
    # Slice STEP 9 — UNLOCK heading body up to (but excluding) the equals-sign
    # banner that precedes the HANDOFF block.
    s = stdout.index("STEP 9 — UNLOCK")
    # The HANDOFF banner row consists of equals signs; find the start of that
    # banner row by locating HANDOFF and walking back to the preceding equals.
    h = stdout.index("HANDOFF (emit on completion)", s)
    # The equals-sign banner is the line directly above the "HANDOFF (..."
    # heading. Trim everything from that banner onward.
    banner_start = stdout.rfind("══", s, h)
    # banner_start lands inside the equals line; back up to its newline.
    nl = stdout.rfind("\n", s, banner_start)
    return stdout[s:nl + 1]


# Byte-identity case: primary + two secondaries (the case used historically).
EXPECTED_PRIMARY_PLUS_TWO = """STEP 9 — UNLOCK
════════════════════════════════════════════════════════════════════════

Before emitting HANDOFF, commit the tdd_state transition so the dispatcher
does not have to commit feature.json manually:

  git add {root}/.claude/features/tdd-subagent/feature.json
  git commit -m "chore(tdd-subagent): advance tdd_state to test-green"

After the test-green transition is committed, capture the impl commit SHA
and close the linked item(s):

  IMPL_SHA=$(git rev-parse HEAD)

  # Primary linked item (closed by impl commit):
  python3 {root}/.claude/features/rabbit-file/scripts/item-status.py set \\
    --feature tdd-subagent --type bug --id BUG-1 \\
    --status close \\
    --reason 'TDD cycle complete' \\
    --fix-commits $IMPL_SHA

  # Secondary linked item (resolved by same impl commit):
  python3 {root}/.claude/features/rabbit-file/scripts/item-status.py set \\
    --feature rabbit-cage --type bug --id BUG-9 \\
    --status close \\
    --reason 'TDD cycle complete (secondary item resolved by same commit)' \\
    --fix-commits $IMPL_SHA

  # Secondary linked item (resolved by same impl commit):
  python3 {root}/.claude/features/rabbit-file/scripts/item-status.py set \\
    --feature other --type backlog --id BL-5 \\
    --status close \\
    --reason 'TDD cycle complete (secondary item resolved by same commit)' \\
    --fix-commits $IMPL_SHA

Remove the scope marker explicitly (no `trap` was registered at LOCK — see
the explanation in STEP 3 about per-call shell process semantics):
  rm -f {root}/.rabbit-scope-active-tdd-subagent

"""


def t_byte_identity():
    tmp = tempfile.mkdtemp()
    try:
        make_root(tmp)
        r = dispatch(tmp, [
            "--linked-item", "/some/features/tdd-subagent/bugs/BUG-1",
            "--item-type", "bug",
            "--linked-items", "rabbit-cage:bug:BUG-9,other:backlog:BL-5",
        ])
        if r.returncode != 0:
            ko(f"byte-identity: dispatch rc={r.returncode}, stderr={r.stderr}")
            return
        block = slice_unlock(r.stdout)
        expected = EXPECTED_PRIMARY_PLUS_TWO.format(root=tmp)
        if block != expected:
            ko("byte-identity: UNLOCK block diverged from expected baseline")
            print("--- GOT ---")
            print(block)
            print("--- WANT ---")
            print(expected)
            return
        ok("byte-identity: UNLOCK close-call block matches baseline")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# Source-shape check: the simplified path no longer defines the old helpers.
def t_helpers_retired():
    with open(DISPATCH) as f:
        src = f.read()
    # The named helpers were the symptom of the over-engineered plumbing
    # (single-use abstractions, multiple parallel accumulators). The
    # simplified pass must not redefine either name.
    if "def _derive_feature_and_id" in src:
        ko("helpers-retired: _derive_feature_and_id still defined")
        return
    if "def _close_call" in src:
        ko("helpers-retired: _close_call still defined")
        return
    # Three parallel accumulator lists collapsed to one.
    if "handoff_closed_items_json_entries" in src:
        ko("helpers-retired: handoff_closed_items_json_entries accumulator still present")
        return
    ok("helpers-retired: legacy _close_call plumbing removed")


t_byte_identity()
t_helpers_retired()

print()
if FAIL == 0:
    print(f"backlog-15 F4 close-call: {PASS} passed.")
    sys.exit(0)
print(f"backlog-15 F4 close-call: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
