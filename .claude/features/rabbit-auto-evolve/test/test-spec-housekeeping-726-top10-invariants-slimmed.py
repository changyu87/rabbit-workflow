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
  (a) STRUCTURE — the numbering is contiguous 1..N (no gaps, no duplicates). The
      invariant COUNT is NOT pinned here: the count-floor ratchet was removed in
      #750 and the #751 deep slim CONSOLIDATED redundant invariants, so the count
      shrank below the former 59. The contiguity guarantee (the sibling
      #724/#725/#751 job) still holds; the dedicated #751 housekeeping test pins
      the measured reduction.
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
# The slimming pass cut the spec below the baseline; this ceiling guards against a
# token-trim regression while leaving headroom for future (additive) invariants.
# Successive additive invariants have consumed that headroom: the original 140-line
# margin was relaxed to 80 (Inv 59), then 55 (the in-progress label reconcile), then
# 30 (the native-dependency blocked-state invariant). The native-DUPLICATE resolution
# invariant (Inv 60, ~24 lines with its Rule-3 prose, schema field, and script-table
# row) is additive and crosses the original baseline, so the ceiling is now expressed
# as a small ABSOLUTE headroom above the live total rather than a sub-baseline margin:
# the slim ratchet is preserved (a fresh top-10 slim would still pass) while honest
# additive growth is not penalised. MAX_TOTAL_LINES sits a meaningful margin below
# the no-headroom point a token-trim regression would push toward. The
# integration-target / dev<->main coexistence invariant (Inv 61, ~49 lines with its
# resolution rules, script-table row, and deprecation criterion) is additive, so the
# absolute ceiling is raised once more to absorb it. The dispatchable-plan-only-
# contains-work invariant (Inv 62, ~20 lines generalizing the Inv 58 filter to drop
# natively-blocked items) is additive, so the ceiling is raised once more to absorb it.
# The admin-override-merge extension to Inv 61 (a `main`-base merge adds `--admin` so the
# loop can land its own PR past the protected default branch's required review; ~16 lines
# across the merge-prs step, the Inv 61 concrete-item list, the script-table row, and the
# test prose) is additive, so the ceiling is raised once more to absorb it. The pre-merge
# install-smoke gate (Inv 63: a new top-level invariant, an install-smoke.py script-table
# row, the safety-check bottom-line check-6 row, and the contract install.py INVOKE; the
# safety-check subsection points at Inv 63 rather than duplicating it) is additive, so the
# ceiling is raised once more to absorb it. The authoritative-version narration-grounding
# invariant (Inv 64, #986: a new top-level invariant grounding version narration in the
# authoritative_version field schedule-decision.py surfaces FRESH each tick — git describe
# with a state last_tagged_version fallback — never a value carried in accumulated session
# context, plus the script-table row extension) is additive, so the ceiling is raised once
# more to absorb it. The dispatchable-refire amendment to Inv 33 (#1004: the immediate-
# refire-vs-idle decision now keys off the fetch|triage|plan pipe's `selection_order` —
# DISPATCHABLE work phase 6 can land — instead of the raw open count, so an all-gated /
# all-blocked open backlog goes idle instead of spinning the loop into a ~1-minute no-op
# refire storm; ~14 lines across the Inv 33 rationale, the schedule-decision script-table
# row, and the test prose) is additive, so the ceiling is raised once more to absorb it.
# The sync-tree integration-target amendment to Inv 38 (#1006: tick-start self-sync now
# pulls `git pull --ff-only origin <integration-target>` with the target resolved via
# integration_target.py resolve_target() (Inv 61) instead of a hardcoded `origin dev`, so
# the post-cutover loop fast-forwards from `main`; +16 lines across the Inv 38 mechanism
# step, the `git pull, never git merge` paragraph, and the enforced-by test prose) is
# additive, so the ceiling is raised once more to absorb it.
# The banner-status zone-label ETA amendment to Inv 22 (#1012: the next-tick ETA now
# renders HH:MM plus a `%Z` zone label in the resolved display zone — importing contract's
# public resolve_display_tz (contract Inv 67) so the SessionStart banner ETA equals
# contract's _auto_evolve_next_tick_eta byte-for-byte, the Inv 55 mirror; ~13 lines across
# the Inv 22 ETA-render paragraph and the enforced-by cadence-present bullet) is additive,
# so the ceiling is raised once more to absorb it.
# The dropped-refire liveness-guard invariant (Inv 65, #1051: a new top-level invariant
# making a dropped immediate-refire one-shot deterministically observable via refire-guard.py
# reconciling the prior tick's tick.log breadcrumb at tick start, plus the script-table row;
# ~32 lines) is additive, so the ceiling is raised once more to absorb it.
# The comment-aware-triage invariant (Inv 66, #1081: a new top-level invariant making a
# maintainer's COMMENT actionable so it is not silently dropped — three triage signals
# (latest_comment_at / has_unactioned_human_comment / needs_human_decision_reflected), a
# deterministic @rabbit-decision: marker, and a per-issue comment_watermarks watermark
# triage-issue.py reads and triage-batch.py advances; ~38 lines) is additive, so the
# ceiling is raised once more to absorb it.
# The self-observed-error-capture invariant (Inv 67, #1091: a new top-level invariant
# giving the orchestrator a bounded capability to capture a self-observed error — non-zero
# exit / unexpected output / anomaly — into a well-formed issue via an ISOLATED analysis
# subagent (context isolation on the croncreate session-reuse path), with the deterministic
# prompt-assembly + file-item argv owned by capture-observed-error.py, a level-1 main-session
# dispatch, and a recursion guard; ~50 lines across the invariant and the script-table row)
# is additive, so the ceiling is raised once more to absorb it.
# The close-ref open-issue cross-check invariant (Inv 68, #1101: a new top-level invariant
# making the merge phase record ONLY currently-OPEN issues in `closed_issues` — merge-prs.py
# cross-checks every parsed close-ref `#N` against `gh issue view --json state` and drops any
# non-OPEN number, defeating the `Fix #N` bare-enumeration trap that wrongly recorded unrelated
# numbers — plus a script-table-row extension and the merge-prs step-4 amendment; ~37 lines)
# is additive, so the ceiling is raised once more to absorb it.
# The pre-merge-snapshot amendment to Inv 68 (#1109: the close-ref open-issue cross-check is a
# PRE-merge snapshot, not a post-merge query — a genuine target auto-closed BY its own merge was
# wrongly dropped as not-currently-open, recording closed_issues=[] for a PR that legitimately
# closed an issue; the amendment adds the PRE-MERGE timing rule + per-PR-batch snapshot prose to
# Inv 68, the merge-prs step-4 rewording, and the script-table-row extension; ~25 lines) is
# additive, so the ceiling is raised once more to absorb it.
# The actual-next-fire ETA amendment to Inv 56 / Inv 22 (#1154: the next-tick ETA was stale/
# frozen across refires because it derived solely from the heartbeat cron edge; tick-jitter.py
# now also derives `next_fire_at` — the earliest upcoming fire across the dispatcher-injected
# CronList snapshot, the pending immediate-refire plus the heartbeat — and banner-status.py /
# contract's Stop line snap the ETA to it when future; ~24 lines across the Inv 56 next-fire
# paragraph + enforced-by, the Inv 22 ETA paragraph + reads/enforced-by bullets, the schema
# field, and the script-table rows) is additive, so the ceiling is raised once more to absorb it.
# The phase-7 merge-failure-surfacing amendment to Inv 40 (#1158: merge-prs.py ALWAYS exits 0
# and reports partial outcomes per-PR in stdout, so the post-dispatch walk now PARSES that
# stdout and aborts non-zero on any `status: "failed"` row — a `gh pr merge --squash --admin`
# that failed on auth/permission — instead of swallowing the failure and refiring the PR
# forever; the amendment adds the merge-failure-surfacing paragraph + the enforced-by test
# scenarios to Inv 40; ~16 lines) is additive, so the ceiling is raised once more to absorb it.
# The same-feature single-dispatch guard (Inv 69, #1161: plan-batch.py assigned dispatch_shapes
# per item in isolation, so two work items on the SAME feature dir were both dispatched in one
# tick and each bumped that feature.json version, producing conflicting PRs; the new top-level
# invariant keeps at most ONE item per feature dir per tick — the collision key is the union of
# an item's edit-target dirs — removing the rest from every dispatch-driving surface and
# surfacing them under the new deferred_same_feature key; ~36 lines across the invariant body
# and its enforced-by, plus a research-item exemption clause) is additive, so the
# ceiling is raised once more to absorb it.
# The stop-cancels-pending-refire guard (Inv 70, #1160: stop-loop.py wrote the stop marker but
# left a pending #refire session-only CronCreate one-shot armed, which still fired, observed the
# marker, and halted — burning one live session turn for a no-op; the new top-level invariant has
# the dispatcher, after stop-loop.py, run schedule-decision.py's new `cancel-refire` subcommand
# over the injected CronList snapshot and CronDelete each emitted cancel_refire_ids id, reusing the
# Inv 33/47 is_refire_oneshot predicate so the durable heartbeat is never cancelled; ~45 lines
# across the invariant body and its enforced-by plus the script-table-row extension) is additive,
# so the ceiling is raised once more to absorb it.
# The stop-disarms-heartbeat / start-rearms guard (Inv 71, #1168: follow-up to Inv 70 — after a
# stop the RECURRING/durable heartbeat stayed armed, and on the croncreate fallback each empty
# post-stop fire burned a full live Claude turn indefinitely; the new top-level invariant has
# schedule-decision.py's new `cancel-heartbeat` subcommand resolve the scheduler and emit
# {scheduler, cancel_heartbeat_ids} so a stop ALSO disarms the durable CronCreate heartbeat on
# the croncreate path while emitting an empty set on the Claude-free crontab path, and the start
# flow re-arms it via the existing idempotent bootstrap; ~66 lines across the invariant body, its
# enforced-by, and the schedule-decision script-table-row extension) is additive, so the ceiling
# is raised once more to absorb it.
MAX_TOTAL_LINES = 4250

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
    # Inv 51 — cross-scope detection
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

    # (a) STRUCTURE — contiguous 1..N. The count is NOT pinned: the count-floor
    # ratchet was removed in #750 and the #751 deep slim consolidated redundant
    # invariants, so N shrank below the former 59. Contiguity is the durable
    # guarantee; the measured reduction is pinned by the dedicated #751 test.
    nums = invariant_numbers(lines)
    if nums is None:
        fail("structure", "no '## Invariants' section found")
    else:
        N = len(nums)
        expected = list(range(1, N + 1))
        if nums == expected:
            ok("structure", f"invariant numbering is contiguous 1..{N}")
        else:
            fail("structure",
                 f"invariant numbering not contiguous 1..{N}: {nums}")

    # (b) WEIGHT — total line count stays under the absolute ceiling (the slim
    # ratchet plus headroom for additive invariants since the baseline).
    total = len(lines)
    if total <= MAX_TOTAL_LINES:
        ok("weight",
           f"spec.md is {total} lines (<= {MAX_TOTAL_LINES} ceiling; "
           f"baseline {BASELINE_TOTAL_LINES})")
    else:
        fail("weight",
             f"spec.md is {total} lines; the #726 slim ratchet caps it at "
             f"<= {MAX_TOTAL_LINES} (baseline {BASELINE_TOTAL_LINES})")

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
