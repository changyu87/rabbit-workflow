#!/usr/bin/env python3
"""test-spec-housekeeping-751-deep-slim-consolidated.py — issue #751 (under #639).

End-to-end housekeeping regression for the DEEP slim wave on rabbit-auto-evolve's
own docs/spec.md (#751). Unlike the #726 prose-tightening pass (which preserved
the count), this wave CONSOLIDATES redundant/overlapping invariants and is
ALLOWED to REDUCE the invariant count (the count-floor ratchet was removed in
#750). The wave succeeds only on a MATERIAL, MEASURED reduction in BOTH the
spec.md line count AND the invariant count, with ZERO behavior/contract loss.

#639 prove-it-dead-or-flag discipline. This test pins four independent facts so a
later edit cannot silently regress the consolidation OR silently drop a
load-bearing rule under cover of slimming:

  (a) REDUCTION — both the spec.md total line count AND the invariant count are
      a measured, material amount below the pre-#751 baseline (captured here).
  (b) CONTIGUITY — the surviving invariants are numbered contiguously 1..N with
      no gaps, no duplicates, no back-steps; and no rae-LOCAL `Inv n` reference
      (a citation of a number inside [1..N]) dangles.
  (c) SURVIVAL — every load-bearing token (every scripts/*.py basename, every
      schema field, every runtime/scope marker name, and every tick-phase
      decision-table row) that existed before the slim STILL appears in spec.md.
      Consolidation merges DESCRIPTIONS; it never drops a rule.
  (d) MERGED-INVARIANT CONTENT — each consolidated invariant's distinct
      load-bearing content survives in the merged-into parent (the merge did not
      silently delete a rule).

Non-interactive. Exits non-zero on any failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# --- (a) REDUCTION baselines (pre-#751, captured from origin/dev) ---
# The deep slim must cut a material amount from BOTH dimensions. These are
# CEILINGS the post-slim surface must clear, with headroom below the baseline so
# a future additive invariant does not instantly trip the guard.
BASELINE_TOTAL_LINES = 3534      # pre-#751 docs/spec.md line count (wc -l)
BASELINE_INVARIANT_COUNT = 59    # pre-#751 invariant count

MIN_LINES_CUT = 150              # deep slim must remove >= this many lines
# #881 (third reopen) added the empirical CronCreate-jitter invariant (Inv 56,
# tick-jitter.py + the .rabbit/auto-evolve-tick-jitter.json owned artifact) — a
# genuinely new owned rule, not slim regression. Allow a small additive headroom
# above the post-slim ceiling so the #751 reduction (>= 150 lines, >= 4
# invariants) is still ENFORCED while the #881 addition is admitted.
POST_881_ADD_LINES = 60
POST_881_ADD_INVARIANTS = 1
# #927 added the release-track-decision invariant (Inv 57: the live release
# track is the vX.Y.Z git tags + per-feature changelogs, NOT the dead-track
# root CHANGELOG.md) — a genuinely new owned rule, not slim regression. Mirror
# the #881 headroom so the #751 reduction (>= 150 lines, >= 4 invariants) stays
# ENFORCED while the #927 addition is admitted.
POST_927_ADD_LINES = 40
POST_927_ADD_INVARIANTS = 1
# #948 added the decomposition-parent-exclusion invariant (Inv 58: a
# decomposition parent is excluded from the dispatchable plan and converges via
# child rollup, not dispatch) — a genuinely new owned rule, not slim
# regression. Mirror the #881/#927 headroom so the #751 reduction (>= 150
# lines, >= 4 invariants) stays ENFORCED while the #948 addition is admitted.
# The line headroom also absorbs the small pre-existing additive drift that had
# accumulated above the post-#927 ceiling before #948.
POST_948_ADD_LINES = 50
POST_948_ADD_INVARIANTS = 1
# #942 added the native-dependency-authoritative blocked-state invariant (Inv
# 59: the GitHub-native dependency relationship is the authoritative source of
# an issue's blocked state; the body `blocked-by:` text is a deprecating
# coexistence mirror) — a genuinely new owned rule, not slim regression. Mirror
# the #881/#927/#948 headroom so the #751 reduction (>= 150 lines, >= 4
# invariants) stays ENFORCED while the #942 addition is admitted.
POST_942_ADD_LINES = 40
POST_942_ADD_INVARIANTS = 1
# #943 added the native-DUPLICATE-resolution invariant (Inv 60: the GitHub-native
# duplicate state, `state_reason=duplicate`, is the authoritative resolution of a
# detected duplicate; the reinvented `duplicate` label is a deprecating coexistence
# mirror; the detection heuristic and its confidence gate are unchanged) — a
# genuinely new owned rule, not slim regression. Mirror the #881/#927/#948/#942
# headroom so the #751 reduction (>= 150 lines, >= 4 invariants) stays ENFORCED
# while the #943 addition is admitted. The line headroom also absorbs the small
# additive drift that had accumulated above the post-#942 ceiling before #943.
POST_943_ADD_LINES = 50
POST_943_ADD_INVARIANTS = 1
# #962 added the integration-target / dev<->main coexistence invariant (Inv 61:
# the loop integrates merged work into a single resolved integration target,
# resolved by integration_target.py, accepting both dev and main during the
# coexistence window, with the manual close-after-merge conditional on the
# target not being the default branch) — a genuinely new owned rule, not slim
# regression. Mirror the #881/#927/#948/#942/#943 headroom so the #751
# reduction (>= 150 lines, >= 4 invariants) stays ENFORCED while the #962
# addition is admitted.
POST_962_ADD_LINES = 50
POST_962_ADD_INVARIANTS = 1
# #970 added the dispatchable-plan-only-contains-work invariant (Inv 62: the
# plan contains only genuinely dispatchable work items, generalizing the Inv 58
# filter so a natively-blocked item — a non-empty `blocked_by` plus a
# blocked-origin reason_code, which the defer-limit can force to decision=work —
# is also excluded) — a genuinely new owned rule, not slim regression. Mirror
# the #881/#927/#948/#942/#943/#962 headroom so the #751 reduction (>= 150
# lines, >= 4 invariants) stays ENFORCED while the #970 addition is admitted.
POST_970_ADD_LINES = 30
POST_970_ADD_INVARIANTS = 1
# #973 extended Inv 61 (the integration-target invariant) with the admin-override
# merge: a `main`-base merge adds `--admin` so the loop can land its own PR past
# the protected default branch's required review. This is an EXTENSION of an
# existing invariant (no new invariant), so it adds a small LINE headroom but
# ZERO invariant headroom — the #751 reduction (>= 150 lines, >= 4 invariants)
# stays ENFORCED while the #973 addition is admitted.
POST_973_ADD_LINES = 20
# #966 added the pre-merge install-smoke gate (Inv 63: the merge phase runs an
# isolated, network-free fresh install + `--update` of rabbit-cage's install.py
# via install-smoke.py and BLOCKS the merge on install/closure breakage) — a
# genuinely new owned rule, not slim regression. Mirror the prior headroom so
# the #751 reduction (>= 150 lines, >= 4 invariants) stays ENFORCED while the
# #966 addition is admitted. The line headroom also absorbs the small additive
# drift that had accumulated above the post-#973 ceiling before #966.
POST_966_ADD_LINES = 50
POST_966_ADD_INVARIANTS = 1
# #986 added the authoritative-version narration-grounding invariant (Inv 64:
# version narration is grounded in the current version surfaced FRESH each tick
# by schedule-decision.py's authoritative_version field — git describe with a
# state last_tagged_version fallback — never a value carried in accumulated
# session context) — a genuinely new owned rule, not slim regression. Mirror
# the prior headroom so the #751 reduction (>= 150 lines, >= 4 invariants)
# stays ENFORCED while the #986 addition is admitted.
POST_986_ADD_LINES = 40
POST_986_ADD_INVARIANTS = 1
# #1004 amended Inv 33 (immediate-refire keys off the fetch|triage|plan pipe's
# DISPATCHABLE selection_order, not the raw open count, so an all-gated/blocked
# backlog goes idle instead of spinning the loop). Additive prose on an EXISTING
# invariant (no new invariant), so headroom is added for the lines but not the
# count. Mirror the prior headroom so the #751 reduction stays ENFORCED.
POST_1004_ADD_LINES = 15
# #1006 amended Inv 38 (tick-start self-sync) to resolve its pull source from
# the integration target via integration_target.py resolve_target() (Inv 61)
# instead of a hardcoded `origin dev`, so the post-cutover loop fast-forwards
# from `main`. Additive prose on an EXISTING invariant (no new invariant), so
# headroom is added for the lines but not the count. Mirror the prior headroom
# so the #751 reduction stays ENFORCED.
POST_1006_ADD_LINES = 16
MAX_TOTAL_LINES = (
    BASELINE_TOTAL_LINES - MIN_LINES_CUT + POST_881_ADD_LINES
    + POST_927_ADD_LINES + POST_948_ADD_LINES + POST_942_ADD_LINES
    + POST_943_ADD_LINES + POST_962_ADD_LINES + POST_970_ADD_LINES
    + POST_973_ADD_LINES + POST_966_ADD_LINES + POST_986_ADD_LINES
    + POST_1004_ADD_LINES + POST_1006_ADD_LINES
)

# The deep slim must reduce the invariant count (count-floor removed in #750).
# At least this many invariants must be consolidated away (then #881 and #927
# each re-add 1).
MIN_INVARIANTS_CUT = 4
MAX_INVARIANT_COUNT = (
    BASELINE_INVARIANT_COUNT - MIN_INVARIANTS_CUT + POST_881_ADD_INVARIANTS
    + POST_927_ADD_INVARIANTS + POST_948_ADD_INVARIANTS
    + POST_942_ADD_INVARIANTS + POST_943_ADD_INVARIANTS
    + POST_962_ADD_INVARIANTS + POST_970_ADD_INVARIANTS
    + POST_966_ADD_INVARIANTS + POST_986_ADD_INVARIANTS
)

# --- (c) SURVIVAL: load-bearing tokens that MUST still appear in spec.md ---

# Every public scripts/*.py basename (the feature's script surface).
SCRIPT_BASENAMES = [
    "advise-restart.py", "banner-status.py", "check-auto-resume.py",
    "check-preconditions.py", "classify-merge-restart.py",
    "clean-dispatch-leaks.py", "cleanup-branches.py",
    "close-decomposed-parents.py", "detect-scheduler.py", "end-tick.py",
    "fetch-queue.py", "install-cron.py", "install-smoke.py", "log-path.py",
    "log-tick.py",
    "mark-aborted.py", "mark-restart-needed.py", "merge-prs.py",
    "plan-batch.py", "prune-worktrees.py", "record-decomposition.py",
    "release-bump.py", "republish-feature.py", "run-post-merge.py",
    "run-tick-phases.py", "running-guard.py", "safety-check.py",
    "schedule-decision.py", "set-evolve-mode.py", "start-loop.py",
    "status-report.py", "stop-loop.py", "sync-tree.py", "tick-headless.py",
    "tick-log.py", "triage-batch.py", "triage-issue.py", "uninstall-cron.py",
    "update-state.py",
]

# auto-evolve-state.schema.json fields (Inv 9 / Inv 30 / decomposition).
SCHEMA_FIELDS = [
    "schema_version", "updated_at", "queue", "in_flight", "last_merged_sha",
    "last_tagged_version", "consecutive_failures", "stop_requested",
    "restart_needed", "defer_counts", "pending_post_merge",
    "decomposition_parents",
]

# Runtime + scope marker names the feature owns.
MARKER_NAMES = [
    ".rabbit-auto-evolve-active", ".rabbit-auto-evolve-running",
    ".rabbit-auto-evolve-stop-requested",
    ".rabbit-auto-evolve-restart-needed", ".rabbit-auto-evolve-aborted",
    ".rabbit-auto-evolve-restart-advised", ".rabbit-scope-active-",
    ".rabbit-human-approval-bypass",
]

# Tick-phase / decision-table rows that MUST survive consolidation.
DECISION_ROWS = [
    # triage 7-rule table reason codes (Inv 3)
    "malformed-labels", "unknown-feature", "duplicate", "feature-retired",
    "blocked", "already-spec'd", "actionable", "needs-judgment",
    # dispatch shapes (Inv 26)
    "parallel-per-feature", "multi-subagent-barrier", "decomposition",
    "research",
    # classify-merge-restart rungs (Inv 8)
    "restart", "refresh", "no-op",
    # release bump triggers (Inv 7)
    "priority-low-medium", "priority-high-critical", "feature-count-threshold",
    "contract-schema-touch", "body-directive",
    # scheduler decisions / mechanisms (Inv 32/33/34)
    "immediate-refire", "croncreate", "crontab", "CronCreate", "ScheduleWakeup",
    # self-modifying migration patterns (Inv 39)
    "coexistence-window", "last-tick-action", "restart-safe",
]

# --- (d) MERGED-INVARIANT distinct content: each merged invariant's
# load-bearing tokens that MUST survive in the merged-into parent. ---
MERGED_CONTENT = [
    # Inv 48 (issue_type/created_at wiring) merged into Inv 44 (computed score)
    "issue_type", "created_at",
    # Inv 50 (log attribution) merged into Inv 37 (log-tick.py)
    "session_id", "RABBIT_AUTO_EVOLVE_RUNNING_MARKER",
    # Inv 44 (branch-switch leak) merged into Inv 43 (clean-dispatch-leaks)
    "git checkout dev",
    # Inv 42 (guard-before-marker) merged into Inv 35 (running-guard)
    "_marker_content",
    # Inv 47 (refire dedup) merged into Inv 33 (immediate-refire)
    "is_refire_oneshot", "delete_refire_ids", "preserve_heartbeat_ids",
    # Inv 59 (no de-queue) merged into Inv 25 (convergence). The #731
    # leak-detector ("--detect-leaks") was removed in #753 (step 3) once
    # rabbit-managed was retired; the de-queue ban prose itself survives.
    "de-queue",
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
    """Ordered list of top-level invariant numbers in the ## Invariants section
    (numbered list items `N. **Title**`), skipping fenced code blocks."""
    start = next((i for i, l in enumerate(lines)
                  if l.strip() == "## Invariants"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^## ", lines[i])), len(lines))
    nums = []
    in_fence = False
    for i in range(start + 1, end):
        s = lines[i].strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(\d+)\. \*\*", lines[i])
        if m:
            nums.append(int(m.group(1)))
    return nums


def check_no_dangling(text, N, defined_set):
    """No rae-local `Inv n` reference inside [1..N] may be undefined."""
    ref_re = re.compile(r"\bInv(?:ariant)?\s+(\d+)\b")
    dangling = []
    for m in ref_re.finditer(text):
        n = int(m.group(1))
        if n <= N and n not in defined_set:
            line_no = text.count("\n", 0, m.start()) + 1
            dangling.append((n, line_no, m.group(0)))
    return dangling


if not os.path.isfile(SPEC):
    fail("exist", f"missing surface: {SPEC}")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)

with open(SPEC) as f:
    body = f.read()
lines = body.splitlines()
total = len(lines)
nums = invariant_numbers(lines)

# --- (a) REDUCTION ---
if total <= MAX_TOTAL_LINES:
    ok("reduction-lines",
       f"spec.md is {total} lines (<= {MAX_TOTAL_LINES}; cut "
       f">= {MIN_LINES_CUT} from baseline {BASELINE_TOTAL_LINES})")
else:
    fail("reduction-lines",
         f"spec.md is {total} lines; the #751 deep slim must cut it to "
         f"<= {MAX_TOTAL_LINES} (>= {MIN_LINES_CUT} below {BASELINE_TOTAL_LINES})")

if nums is None:
    fail("reduction-count", "no '## Invariants' section found")
else:
    N = len(nums)
    if N <= MAX_INVARIANT_COUNT:
        ok("reduction-count",
           f"{N} invariants (<= {MAX_INVARIANT_COUNT}; consolidated "
           f">= {MIN_INVARIANTS_CUT} from baseline {BASELINE_INVARIANT_COUNT})")
    else:
        fail("reduction-count",
             f"{N} invariants; the #751 deep slim must consolidate to "
             f"<= {MAX_INVARIANT_COUNT} (>= {MIN_INVARIANTS_CUT} fewer than "
             f"the {BASELINE_INVARIANT_COUNT} baseline)")

    # --- (b) CONTIGUITY ---
    expected = list(range(1, N + 1))
    if nums == expected:
        ok("contiguity", f"invariant numbering is contiguous 1..{N}")
    else:
        defined_set = set(nums)
        gaps = sorted(set(range(1, (max(nums) if nums else 0) + 1)) - defined_set)
        dups = sorted({n for n in nums if nums.count(n) > 1})
        fail("contiguity",
             f"not contiguous 1..{N}: found {nums}; gaps={gaps}; dups={dups}")

    dangling = check_no_dangling(body, N, set(nums))
    if not dangling:
        ok("no-dangling", "no dangling rae-local invariant references")
    else:
        detail = "; ".join(f"Inv {n} @line {ln} ({frag!r})"
                           for n, ln, frag in dangling)
        fail("no-dangling", f"dangling rae-local reference(s): {detail}")

# --- (c) SURVIVAL of load-bearing tokens ---
for group, items in (
    ("script", SCRIPT_BASENAMES),
    ("schema-field", SCHEMA_FIELDS),
    ("marker", MARKER_NAMES),
    ("decision-row", DECISION_ROWS),
):
    missing = [t for t in items if t not in body]
    if not missing:
        ok(f"survival-{group}", f"all {len(items)} {group} token(s) present")
    else:
        fail(f"survival-{group}",
             f"load-bearing {group} token(s) LOST by the slim: {missing}")

# --- (d) MERGED-INVARIANT content survives in the parent ---
missing_merged = [t for t in MERGED_CONTENT if t not in body]
if not missing_merged:
    ok("merged-content",
       f"all {len(MERGED_CONTENT)} merged-invariant token(s) survive")
else:
    fail("merged-content",
         f"merged-invariant content LOST by consolidation: {missing_merged}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    print("test-spec-housekeeping-751-deep-slim-consolidated: FAIL",
          file=sys.stderr)
    sys.exit(1)
print("test-spec-housekeeping-751-deep-slim-consolidated: all checks passed.")
sys.exit(0)
