#!/usr/bin/env python3
"""test-wave-automerge.py — E2E for the gated wave auto-merge decision script.

Drives scripts/wave-automerge.py as a subprocess. The script owns the
script-tier gating decision a user-installed /rabbit-housekeep run uses to
auto-merge a wave's PR on green gates (issue #1191): it reads the wave's
HANDOFF gates, the PR mergeable/CI state, and the honest-reduction verdict,
and emits `decision: merge` only when ALL hold — else `leave-open`. The
gating logic is testable WITHOUT shelling out to `gh`: every signal is passed
in via the JSON payload on stdin.

  t0: script exists and is executable.
  t1: all gates green + honest `reduced` verdict -> decision: merge.
  t2: an honest `no-op` verdict (already-clean wave) STILL merges -- a no-op is
      a passing reduction outcome (#1190 honesty semantics).
  t3: tdd_state != test-green -> decision: leave-open (gate failed).
  t4: test_result != pass -> decision: leave-open.
  t5: spec_compliance != pass -> decision: leave-open.
  t6: PR not mergeable / not clean -> decision: leave-open.
  t7: CI checks not green -> decision: leave-open.
  t8: a failed gate is named in the decision's `reasons`, so the leave-open
      verdict is auditable (machine-first).
  t9: invocation error (bad/empty JSON) exits 2.

Non-interactive. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import subprocess
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "wave-automerge.py")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def decide(payload):
    """Run `wave-automerge.py decide` feeding payload as JSON on stdin."""
    return subprocess.run(
        ["python3", SCRIPT, "decide"],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )


def green_payload(**overrides):
    """A fully-green payload; overrides mutate individual signals."""
    p = {
        "pr": 4242,
        "tdd_state": "test-green",
        "test_result": "pass",
        "spec_compliance": "pass",
        "verdict": "reduced",
        "mergeable": "MERGEABLE",
        "merge_state_status": "CLEAN",
        "ci_status": "pass",
    }
    p.update(overrides)
    return p


# t0
if not (os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK)):
    fail("t0", f"missing or non-executable: {SCRIPT}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "wave-automerge.py exists and is executable")

# t1: all green + reduced -> merge
r = decide(green_payload())
if r.returncode == 0 and json.loads(r.stdout).get("decision") == "merge":
    ok("t1", "all gates green + reduced verdict -> merge")
else:
    fail("t1", f"expected merge; rc={r.returncode} out={r.stdout} err={r.stderr}")

# t2: honest no-op still merges
r = decide(green_payload(verdict="no-op"))
if r.returncode == 0 and json.loads(r.stdout).get("decision") == "merge":
    ok("t2", "honest no-op verdict still merges (passing outcome)")
else:
    fail("t2", f"expected merge for no-op; rc={r.returncode} out={r.stdout}")

# t3: tdd_state gate
r = decide(green_payload(tdd_state="test-red"))
if r.returncode == 0 and json.loads(r.stdout).get("decision") == "leave-open":
    ok("t3", "tdd_state != test-green -> leave-open")
else:
    fail("t3", f"expected leave-open; out={r.stdout}")

# t4: test_result gate
r = decide(green_payload(test_result="fail"))
if r.returncode == 0 and json.loads(r.stdout).get("decision") == "leave-open":
    ok("t4", "test_result != pass -> leave-open")
else:
    fail("t4", f"expected leave-open; out={r.stdout}")

# t5: spec_compliance gate
r = decide(green_payload(spec_compliance="fail"))
if r.returncode == 0 and json.loads(r.stdout).get("decision") == "leave-open":
    ok("t5", "spec_compliance != pass -> leave-open")
else:
    fail("t5", f"expected leave-open; out={r.stdout}")

# t6: PR mergeable / clean gate
r = decide(green_payload(merge_state_status="DIRTY"))
if r.returncode == 0 and json.loads(r.stdout).get("decision") == "leave-open":
    ok("t6", "PR not clean -> leave-open")
else:
    fail("t6", f"expected leave-open; out={r.stdout}")

# t7: CI green gate
r = decide(green_payload(ci_status="fail"))
if r.returncode == 0 and json.loads(r.stdout).get("decision") == "leave-open":
    ok("t7", "CI not green -> leave-open")
else:
    fail("t7", f"expected leave-open; out={r.stdout}")

# t8: failed gate named in reasons
r = decide(green_payload(tdd_state="test-red", ci_status="fail"))
out = json.loads(r.stdout) if r.returncode == 0 else {}
reasons = " ".join(out.get("reasons", []))
if out.get("decision") == "leave-open" and "tdd_state" in reasons and "ci" in reasons.lower():
    ok("t8", "failed gates named in reasons (auditable)")
else:
    fail("t8", f"expected named reasons; out={r.stdout}")

# t9: invocation error exits 2
r = subprocess.run(
    ["python3", SCRIPT, "decide"], input="not json",
    capture_output=True, text=True,
)
if r.returncode == 2:
    ok("t9", "bad JSON payload exits 2")
else:
    fail("t9", f"expected exit 2; rc={r.returncode}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
