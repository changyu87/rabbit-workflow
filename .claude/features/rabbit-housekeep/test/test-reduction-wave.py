#!/usr/bin/env python3
"""test-reduction-wave.py — E2E gate for the measured-reduction housekeeping
wave run against rabbit-housekeep's own doc surfaces.

This test IS the housekeeping test pattern the feature mandates, applied to
the feature itself: it drives the real measure-reduction.py against the live
doc surfaces and asserts BOTH halves of a wave's contract.

  t0: MEASURED REDUCTION — the live doc surfaces (docs/spec.md,
      docs/contract.md, skills/rabbit-housekeep/SKILL.md) total strictly
      fewer lines than the pre-wave baseline. The verdict is computed by
      measure-reduction.py `count` + `diff` (script-tier, not judgment): the
      diff against the recorded pre-wave snapshot reports reduced=true with a
      negative total_delta. A reword that left totals flat would FAIL here.

  t1: LOAD-BEARING SURVIVAL — every named load-bearing token (script name,
      subcommand names, exit codes, schema/verdict fields, the verbatim §6
      markers, the nesting-constraint tokens, and contract relationships)
      is still present somewhere in the doc surfaces after the wave.

Non-interactive. Exits non-zero on failure.

Version: 0.2.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import json
import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "measure-reduction.py")

SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")
CONTRACT = os.path.join(FEATURE_DIR, "docs", "contract.md")
SKILL = os.path.join(FEATURE_DIR, "skills", "rabbit-housekeep", "SKILL.md")
DOC_SURFACES = [SPEC, CONTRACT, SKILL]

# Pre-wave baseline, snapshotted by measure-reduction.py count before the
# reduction wave edited the doc surfaces. The wave must drive the live total
# strictly below this.
PRE_WAVE_BASELINE = {
    SPEC: 154,
    CONTRACT: 79,
    SKILL: 194,
    "__total__": 427,
}

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


# t0: measured reduction, via the real count + diff path.
with tempfile.TemporaryDirectory() as tmp:
    before = os.path.join(tmp, "before.json")
    after = os.path.join(tmp, "after.json")
    with open(before, "w") as f:
        json.dump(PRE_WAVE_BASELINE, f)
    count = subprocess.run(
        ["python3", SCRIPT, "count", *DOC_SURFACES],
        capture_output=True, text=True,
    )
    if count.returncode != 0:
        fail("t0", f"count exited {count.returncode}; stderr={count.stderr}")
    else:
        with open(after, "w") as f:
            f.write(count.stdout)
        diff = subprocess.run(
            ["python3", SCRIPT, "diff", before, after],
            capture_output=True, text=True,
        )
        d = json.loads(diff.stdout)
        if d.get("reduced") is True and d.get("total_delta", 0) < 0:
            ok("t0", f"doc surfaces reduced (total_delta={d['total_delta']})")
        else:
            fail("t0", f"no measured reduction vs pre-wave baseline: {d}")

# t1: load-bearing token survival across the doc surfaces.
blob = ""
for p in DOC_SURFACES:
    with open(p, encoding="utf-8") as f:
        blob += f.read() + "\n"

REQUIRED_TOKENS = [
    # script + interface
    "measure-reduction.py",
    "count",
    "diff",
    "total_delta",
    "reduced",
    "per_artifact",
    "removed_paths",
    "added_paths",
    # exit codes
    "`0` success",
    "`2` invocation error",
    # verbatim §6 embed markers
    "BEGIN VERBATIM coding-rules.md §6",
    "END VERBATIM coding-rules.md §6",
    "## 6. Cleanup: Prove It Dead or Flag It",
    # nesting constraint tokens
    "subagent-dispatching",
    "two-level",
    "Agent(",
    # cross-feature relationships
    "rabbit-feature-touch",
    "tdd-subagent",
    "file-item.py",
    "record-decomposition.py",
    "close-decomposed-parents.py",
    "rabbit-decompose",
    "rabbit-auto-evolve",
]
missing = [t for t in REQUIRED_TOKENS if t not in blob]
if missing:
    fail("t1", f"load-bearing tokens missing after wave: {missing}")
else:
    ok("t1", f"all {len(REQUIRED_TOKENS)} load-bearing tokens survive")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
