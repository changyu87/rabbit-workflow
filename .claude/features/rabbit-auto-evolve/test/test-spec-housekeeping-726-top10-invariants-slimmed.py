#!/usr/bin/env python3
"""test-spec-housekeeping-726-top10-invariants-slimmed.py — issue #726 (under #639).

End-to-end content regression that rabbit-auto-evolve's live docs/spec.md has had
its TEN LARGEST invariants slimmed by a measured prose-tightening pass (#726): the
verbose halves — duplicated explanation, restated rationale, repeated examples — were
cut while every normative/load-bearing statement, MUST/MUST-NOT rule, script name,
schema field, decision-table row, and cross-reference was PRESERVED.

The pass is "weight loss, not a reword": this test pins three independent facts so a
later edit cannot silently regress the slimming OR silently delete an invariant /
load-bearing phrase under the cover of slimming.

#639 discipline:
  (a) STRUCTURE — every invariant remains present and the numbering is contiguous
      1..N (no invariant deleted, none renumbered; that is the sibling #724/#725 job).
      The count grows only by APPENDING (issue #731 appended Inv 59); the guard pins
      the current count so a deletion or a renumber still fails.
  (b) WEIGHT    — the spec.md total line count stays a meaningful margin below the
      pre-#726 baseline (3594 lines). A trivial token-trim would not clear the ceiling.
      The ceiling carries headroom for future (additive) invariants below the baseline.
  (c) CONTENT   — a sample of load-bearing literals that the top-10 invariants carry
      (script names, schema fields, decision-table tokens, MUST cross-refs) is STILL
      present, so the line drop cannot have come from cutting a binding rule.

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Pre-#726 baseline total line count of docs/spec.md.
BASELINE_TOTAL_LINES = 3594
# The slimming pass must keep the spec total at least this many lines below the
# baseline. This is a floor, not the achieved figure: it guards against a token-trim
# regression while leaving headroom for future (additive) invariants. Issue #731
# appended Inv 59 (~50 lines), so the ceiling is relaxed from the original 140-line
# margin to an 80-line margin — still well below the baseline.
MIN_LINES_CUT = 80
MAX_TOTAL_LINES = BASELINE_TOTAL_LINES - MIN_LINES_CUT

# Load-bearing literals carried by the ten slimmed invariants (Inv 3, 32, 4, 6, 7,
# 30, 56, 1, 18, 29). Each is a script name, schema field, decision token, or a
# MUST/cross-ref that a sibling test or the contract gate pins — the slimming pass
# MUST keep every one of these.
REQUIRED_PHRASES = [
    # Inv 3 — triage-issue.py seven-rule decision table
    "triage-issue.py",
    "close-not-planned",
    "malformed-labels",
    "needs-judgment",
    "comment-thread reconciliation",
    # Inv 32 — cron scheduling
    "tick-headless.py",
    "install-cron.py",
    "uninstall-cron.py",
    "CronCreate",
    "ScheduleWakeup",
    # Inv 4 — plan-batch.py
    "plan-batch.py",
    "barrier_first",
    "computed_scores",
    "--max-parallel",
    "research_items",
    # Inv 6 — merge-prs.py + cleanup-branches.py
    "merge-prs.py",
    "cleanup-branches.py",
    "safety-check.py",
    "--squash",
    # Inv 7 — release-bump.py
    "release-bump.py",
    "--features-threshold",
    "priority-low-medium",
    # Inv 30 — run-post-merge.py
    "run-post-merge.py",
    "pending_post_merge",
    "--record-pending",
    # Inv 56 — cross-scope detection
    "cross_scope",
    "cross_scope_items",
    "parallel-per-feature",
    "parent-reference line",
    # Inv 1 — set-evolve-mode.py
    "set-evolve-mode.py",
    "/rabbit-auto-evolve start",
    # Inv 18 — triage-batch.py
    "triage-batch.py",
    "defer_counts",
    "defer-limit-reached",
    # Inv 29 — status-report.py
    "status-report.py",
    "markers_present",
]

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


def invariant_numbers(lines):
    """Return the ordered list of top-level invariant numbers in the
    ## Invariants section (numbered list items of the form `N. **Title.**`)."""
    start = next((i for i, l in enumerate(lines)
                  if l.strip() == "## Invariants"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^## ", lines[i])), len(lines))
    nums = []
    for i in range(start + 1, end):
        m = re.match(r"^(\d+)\. \*\*", lines[i])
        if m:
            nums.append(int(m.group(1)))
    return nums


if not os.path.isfile(SPEC):
    fail("exist", f"missing surface: {SPEC}")
else:
    with open(SPEC) as f:
        body = f.read()
    lines = body.splitlines()

    # (a) STRUCTURE — 59 invariants, contiguous 1..59 (Inv 59 appended by #731).
    EXPECTED_COUNT = 59
    nums = invariant_numbers(lines)
    if nums is None:
        fail("structure", "no '## Invariants' section found")
    else:
        if len(nums) == EXPECTED_COUNT:
            ok("structure", f"exactly {EXPECTED_COUNT} invariants present")
        else:
            fail("structure",
                 f"expected {EXPECTED_COUNT} invariants, found {len(nums)}")
        expected = list(range(1, EXPECTED_COUNT + 1))
        if nums == expected:
            ok("structure",
               f"invariant numbering is contiguous 1..{EXPECTED_COUNT}")
        else:
            fail("structure",
                 f"invariant numbering not contiguous 1..{EXPECTED_COUNT}: {nums}")

    # (b) WEIGHT — total line count dropped by a meaningful margin.
    total = len(lines)
    if total <= MAX_TOTAL_LINES:
        ok("weight",
           f"spec.md is {total} lines (<= {MAX_TOTAL_LINES}; cut "
           f">= {MIN_LINES_CUT} from baseline {BASELINE_TOTAL_LINES})")
    else:
        fail("weight",
             f"spec.md is {total} lines; the #726 slim pass must cut it to "
             f"<= {MAX_TOTAL_LINES} (>= {MIN_LINES_CUT} lines below the "
             f"{BASELINE_TOTAL_LINES} baseline)")

    # (c) CONTENT — load-bearing literals survive the slimming.
    for phrase in REQUIRED_PHRASES:
        if phrase in body:
            ok("content", f"load-bearing literal present: {phrase!r}")
        else:
            fail("content",
                 f"load-bearing literal LOST by the slim pass: {phrase!r}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-housekeeping-726-top10-invariants-slimmed: FAIL",
          file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-726-top10-invariants-slimmed: all checks passed.")
sys.exit(0)
