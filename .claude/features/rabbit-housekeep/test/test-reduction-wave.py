#!/usr/bin/env python3
"""test-reduction-wave.py — E2E gate for the measured-reduction housekeeping
wave run against rabbit-housekeep's own doc surfaces.

This test IS the housekeeping test pattern the feature mandates, applied to
the feature itself: it drives the real measure-reduction.py against the live
doc surfaces and asserts BOTH halves of a wave's contract.

  t0: MEASURED CEILING — the live doc surfaces (docs/spec.md,
      docs/contract.md, skills/rabbit-housekeep/SKILL.md) total no MORE lines
      than the recorded ceiling. The verdict is computed by
      measure-reduction.py `count` + `diff` (script-tier, not judgment): the
      diff against the recorded ceiling snapshot reports a non-positive
      total_delta. A reword/bloat that pushed totals above the ceiling would
      FAIL here. The ceiling is refreshed after each governed touch that
      adds behavior additively (e.g. v0.3.0 added the script-backed-
      orchestration dimension), so it keeps guarding future reword-bloat
      without forbidding additive growth.

  t1: LOAD-BEARING SURVIVAL — every named load-bearing token (script names,
      subcommand names, exit codes, schema/verdict fields, the verbatim §6
      and §4 markers, the nesting-constraint tokens, and contract
      relationships) is still present somewhere in the doc surfaces.

Non-interactive. Exits non-zero on failure.

Version: 0.4.0
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

# Recorded ceiling, snapshotted by measure-reduction.py count after the last
# governed touch. The live total must stay at or below this; a reword/bloat
# that pushed it higher FAILS. Refreshed when a governed touch adds behavior
# additively (v0.3.0: script-backed-orchestration dimension; v0.4.0:
# illustrative-example scanner exemption; v0.5.0: user-facing command +
# consuming-project scope resolution).
DOC_CEILING = {
    SPEC: 255,
    CONTRACT: 86,
    SKILL: 258,
    "__total__": 599,
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


# t0: measured ceiling, via the real count + diff path. The diff is
# ceiling(before) vs live(after): a non-positive total_delta means the live
# surfaces are at or below the recorded ceiling.
with tempfile.TemporaryDirectory() as tmp:
    before = os.path.join(tmp, "before.json")
    after = os.path.join(tmp, "after.json")
    with open(before, "w") as f:
        json.dump(DOC_CEILING, f)
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
        if d.get("total_delta", 1) <= 0:
            ok("t0", f"doc surfaces at or below ceiling (total_delta={d['total_delta']})")
        else:
            fail("t0", f"doc surfaces grew above recorded ceiling: {d}")

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
    # script-backed-orchestration dimension + verbatim §4 embed markers
    "check-script-backed.py",
    "scan",
    "BEGIN VERBATIM spec-rules.md §4 Script-Backed Orchestration",
    "END VERBATIM spec-rules.md §4 Script-Backed Orchestration",
    "runtime-placeholder",
    "computed-value",
    "mode-aware-branching",
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
