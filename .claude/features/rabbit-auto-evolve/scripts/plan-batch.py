#!/usr/bin/env python3
"""plan-batch.py — conflict-graph + barrier dispatch planner (Inv 4, Inv 26).

Reads a JSON array of triage objects on stdin (the caller passes only
items whose decision == "work") and emits a deterministic dispatch plan
on stdout:

  {
    "selection_order": [602, 601, 700],
    "dispatch_shapes": {"602": "multi-subagent-barrier", "601": "parallel-per-feature", "700": "research"},
    "computed_scores": {"602": 0.63, "601": 0.41, "700": 0.30},
    "barrier_first": [123, 124],
    "groups": [[125, 126], [127]],
    "research_items": [700],
    "cross_scope_items": [602],
    "self_modifying_migrations": {"125": "coexistence-window"},
    "restart_needed": [127]
  }

Two decoupled decisions (Inv 26 / issue #435):

  STAGE 1 — work selection (`selection_order`). Dispatch-shape BLIND:
  ordered by the composite key (computed_score desc, contract_touch desc,
  issue asc) per issue #441 (refining #479) — the loop's OWN computed
  priority score is PRIMARY, the contract-touch barrier is the SECONDARY
  tiebreak (contract items lead WITHIN a score tier, never across tiers),
  issue asc is the final stable tiebreak. The score is a deterministic
  weighted blend of observable signals (filer `priority:` label,
  blocking-fanout, scope size, bug-vs-enhancement, age) computed in this
  script — the filer label is ONE input among several, no longer the sole
  determinant, so a mislabeled or stale-priority issue is ordered sensibly
  (issue #441). This is the SAME key that drives barrier_first, so the two
  always agree on ordering. It MUST NOT consult dispatch shape, feature
  count for *shape* purposes, or "knows how" (contract_touch is a
  barrier/conflict property, not a dispatch shape). The computed score per
  item is emitted under `computed_scores` (issue-number string -> float in
  [0, 1]) for transparency. Work-only (items whose decision != "work" are
  dropped).

  STAGE 2 — dispatch shape (`dispatch_shapes`, issue-number-string -> shape).
  Per work item, choose the FIRST fitting shape from exactly three:
    - `decomposition`          when the item touches >= --decompose-threshold
                               distinct feature dirs (default 10) — split into
                               per-feature sub-issues, each re-enters dispatch.
    - `multi-subagent-barrier` when the item touches >1 feature dir (below
                               the threshold) — per-feature subagents land
                               serially on one shared branch, each a full
                               single-feature touch with its own scope marker.
    - `parallel-per-feature`   when the item touches exactly one feature dir —
                               the performance preference (NOT a correctness
                               requirement).
  An item's feature count is `len(item["features"])` (the set emitted by
  triage-issue.py), falling back to 1 (the single `feature` label) when
  `features` is absent. An item triage flagged `cross_scope: true` (its BODY
  spans multiple feature dirs — Inv 51 / issue #433) is NEVER shaped
  parallel-per-feature even when its feature count is 1; the body-derived
  cross_scope signal forces multi-subagent-barrier (below the threshold) or
  decomposition (at/above it), and the item is listed under the
  `cross_scope_items` output key. The struck shape 2 (sequential single-subagent
  with a persistent `.rabbit-scope-override session`) is NEVER emitted — bounded
  scope is a hard constraint, not waivable by autonomy (maintainer policy on
  issue #435). No shape writes any marker; this script is a pure processor.

Algorithm for barrier_first / groups (per spec.md Inv 4 / Inv 44 / design
doc §6; computed-score-primary, barrier-secondary per issue #441 refining
#479):
  1. Sort ALL work items by the composite key
     (computed_score desc, contract_touch_rank, issue): the loop-computed
     priority score is PRIMARY (higher score dispatches first), the
     contract-touch barrier is the SECONDARY tiebreak (contract items
     lead WITHIN a score tier), issue ascending is the final stable
     tiebreak. A higher-scoring non-contract item therefore beats a
     lower-scoring contract item.
  2. barrier_first is the leading run of contract_touch items in that
     sorted order (the contract items before the first non-contract
     item). If the top item is non-contract, barrier_first is empty. The
     remainder (from the first non-contract item onward) feeds grouping.
  3. Build a conflict graph on the remainder; an edge exists between A
     and B iff A.feature == B.feature.
  4. Greedy graph-color the remainder, walking in composite-key order;
     each item takes the lowest color number with no same-feature
     neighbor.
  5. Apply --max-parallel cap (default 4): any color partition larger
     than the cap is split into consecutive sub-groups of size <= cap.

A 4th dispatch shape, `research` (Inv 27 / issue #478), handles
research/investigation items (decision == "research" from triage). They
produce FINDINGS, not code: they appear in `selection_order` (same
composite sort), carry `dispatch_shapes[issue] == "research"`, and are
listed under the always-present `research_items` key — but NEVER enter
`barrier_first` or the conflict-graph `groups` (findings edit no code).

SELF-MODIFYING MIGRATIONS (the self-modifying-migration invariant). A work
item that changes loop-critical runtime state (a marker the tick driver reads,
a resolved path, an agent type the loop dispatches, a session config key) is
tagged in `self_modifying_migrations` (issue-number-string -> safe-execution
pattern) with the pattern chosen by HOW the loop consumes the thing:
  - re-read from disk each tick -> coexistence-window (no restart)
  - self-contained              -> last-tick-action   (no restart)
  - held in session memory      -> restart-safe        (restart NEXT session)
The token->consumption mapping is the data-driven
`schemas/self-modifying-migration-registry.json`. Items whose pattern is
restart-safe are listed under `restart_needed`; the tick driver (not this
processor) sets the .rabbit-auto-evolve-restart-needed marker for them and
ends the tick cleanly. The loop NEVER stops to ask a human for a
self-modifying migration.

DECOMPOSITION-PARENT EXCLUSION (issue #948). A recorded decomposition parent
— an OPEN issue triage flagged `decomposition_parent: true` (it HAS
GitHub-native sub-issues, `sub_issues_summary.total > 0`, OR is a key in the
`decomposition_parents` state map during coexistence) — is FILTERED OUT of the
dispatchable plan: it is neither selected (`selection_order`) nor shaped
(`dispatch_shapes`) nor listed in `cross_scope_items`. A decomposition parent
carries no own code change; it converges via child rollup (closed by
close-decomposed-parents.py once all children close, Inv 53), never via
dispatch, so it must NEVER reach a TDD subagent. The parent stays OPEN and
tracked-by-decomposition — an existing non-work tracked outcome, so the
exclusion does not violate the convergence guarantee (Inv 25). A child
sub-issue (it has a PARENT link but no children of its own, so
`decomposition_parent` is false) is dispatched normally.

NATIVELY-BLOCKED EXCLUSION (issue #970, Inv 62). An item still carrying a
non-empty `blocked_by` list — the OPEN native blocker numbers triage-issue.py
emits from the GitHub-native dependencies graph (the authoritative blocked
source, Inv 59) — TOGETHER WITH a blocked-origin `reason_code` (`blocked` from
rule 5, or `defer-limit-reached` after a force-promotion) is FILTERED OUT of the
dispatchable plan even when its `decision` reads `work`. triage-batch.py's
anti-infinite-defer counter (Inv 18) can FORCE a repeatedly-deferred item to
`decision=work` (`reason_code=defer-limit-reached`); that lifts the defer verdict
but does NOT clear an open blocker, so the decision-only drop alone would let a
still-blocked item through. Filtering on the `blocked_by` + blocked-origin-
`reason_code` signal at the same point as the Inv 58 parent filter keeps it out
of selection_order, dispatch_shapes, and cross_scope_items. The reason_code gate
spares a `blocked_by` carried purely as a cross-item blocking-fanout signal
(Inv 44) on an actionable item. The item stays OPEN and tracked-by-dependency
(no Inv 25 violation) and re-enters the plan once its blocker closes.

The script is a pure JSON processor — no gh, no git, no filesystem
mutations.

Exit code: 0 on success; non-zero on malformed stdin JSON or invalid
--max-parallel / --decompose-threshold value.

Version: 1.8.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import json
import os
import sys


PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_NO_PRIORITY_RANK = 4

# Self-modifying-migration safe-execution patterns (the self-modifying-migration
# invariant). A self-modifying migration is a work item that changes something
# the loop itself depends on at runtime; the safe-execution pattern is chosen by
# HOW the loop consumes the thing. The one yield point is the restart-needed
# marker (PATTERN_RESTART_SAFE), never a human stop.
PATTERN_COEXISTENCE = "coexistence-window"   # re-read from disk each tick
PATTERN_LAST_TICK = "last-tick-action"       # self-contained; firewall on tick boundary
PATTERN_RESTART_SAFE = "restart-safe"        # held in session memory -> restart next session

# The registry data file mapping loop-critical runtime state to consumption
# type (and thence to pattern). Loaded once at module import.
_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "schemas", "self-modifying-migration-registry.json",
)


def _load_registry():
    """Load the loop-critical runtime-state registry. Returns
    (entries, consumption_to_pattern). Tokens are matched case-insensitively
    against an item's title+body text."""
    with open(_REGISTRY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", []), data.get("consumption_to_pattern", {})


_SMM_ENTRIES, _SMM_CONSUMPTION_TO_PATTERN = _load_registry()


def _self_modifying_pattern(item):
    """Classify a work item as a self-modifying migration and return the safe-
    execution pattern, or None if the item touches no loop-critical runtime
    state.

    Detection scans the item's title+body for registry tokens. Pattern
    precedence (the consumption-based decision rule):
      1. any matched state held in session memory (memory-at-start) ->
         restart-safe (the change takes effect NEXT session; the loop sets the
         .rabbit-auto-evolve-restart-needed marker and ends the tick cleanly).
      2. else, an item that flags `self_contained` -> last-tick-action (do all
         other work first; migrate as the final action; the tick boundary is
         the firewall).
      3. else (state re-read from disk each tick) -> coexistence-window
         (additive-then-remove; honor BOTH old+new during the transition).
    """
    text = ((item.get("title") or "") + " " + (item.get("body") or "")).lower()
    matched = [e for e in _SMM_ENTRIES
               if e.get("token", "").lower() in text]
    if not matched:
        return None
    consumptions = {e.get("consumption") for e in matched}
    if "memory-at-start" in consumptions:
        return PATTERN_RESTART_SAFE
    if item.get("self_contained"):
        return PATTERN_LAST_TICK
    return PATTERN_COEXISTENCE


# ---------------------------------------------------------------------------
# Loop-computed priority score (issue #441)
# ---------------------------------------------------------------------------
# The loop computes its OWN priority signal from observable, hard-to-game
# evidence rather than blindly trusting the filer-set `priority:` label. The
# filer label remains ONE input among several (weight reduced); it is no
# longer the sole determinant. Every signal is computed DETERMINISTICALLY in
# this script (script-tier, never LLM inference) from data already flowing
# through the triage objects on stdin — no gh/git/filesystem reads.
#
# Reconciliation with issue #479: #479 made the filer `priority:` label the
# PRIMARY composite-sort key with the contract-touch barrier as the SECONDARY
# tiebreak. #441 REFINES that: the loop's `computed_score` is now the PRIMARY
# key; the contract-touch barrier is PRESERVED as the SECONDARY tiebreak (it
# is a barrier/conflict property required for Inv 26 grouping correctness, not
# a priority signal), and issue number remains the final stable tiebreak. The
# filer label is folded INTO the score as one weighted input, so it still
# influences ordering but can no longer single-handedly jump an item ahead.
#
# Signals deterministically observable in the triage batch (issue #441's
# proposed signal table, restricted to the deterministic subset):
#   - Filer-set label  (the `priority` field)            weight 0.15
#   - Blocking-fanout  (other batch items blocked-by N)  weight 0.30
#   - Scope size       (smaller `features` set = boost)  weight 0.10
#   - Bug vs. enhancement (`issue_type` == "bug")        small boost 0.05
#   - Age              (older `created_at` = mild boost)  weight 0.05
# The remaining proposed signals (recurrence-count, test-coverage-delta) are
# NOT deterministically computable in this pure JSON processor (they require
# fuzzy symptom matching / running each feature's test suite) and are left to
# a follow-up; see the spec invariant's deferred-signals note.
_W_FILER = 0.15
_W_FANOUT = 0.30
_W_SCOPE = 0.10
_W_BUG = 0.05
_W_AGE = 0.05

# Filer-label signal value: critical=1.0 .. low=0.25, no/unknown label=0.0
# (a missing label contributes nothing rather than masquerading as low).
_FILER_VALUE = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}

# Fanout normalization cap: a blocking-fanout of this many or more other items
# saturates the fanout signal at 1.0. Keeps the score bounded in [0, 1].
_FANOUT_CAP = 5

# Age normalization cap (days): an item this old or older saturates the age
# signal at 1.0.
_AGE_CAP_DAYS = 30.0


def _feature_count_for_score(item):
    """Distinct feature-dir count for the scope-size signal. Mirrors
    _feature_count (prefers `features`, falls back to 1)."""
    feats = item.get("features")
    if isinstance(feats, list) and feats:
        return len(feats)
    return 1


def _fanout_counts(items):
    """Blocking-fanout per issue: the number of OTHER items in the batch that
    declare a `blocked-by` dependency on it (issue #441). A foundational item
    that unblocks others should rise. This is hard for a filer to self-elevate
    because it requires OTHER issues to actually reference yours.

    Returns a dict issue_number -> fanout count."""
    counts = {}
    for it in items:
        for dep in it.get("blocked_by", []) or []:
            try:
                dep_n = int(dep)
            except (TypeError, ValueError):
                continue
            counts[dep_n] = counts.get(dep_n, 0) + 1
    return counts


def _age_days(item):
    """Days since the item's `created_at` ISO-8601 UTC timestamp, or 0.0 when
    absent/unparseable (age then contributes nothing — no crash)."""
    created = item.get("created_at")
    if not created:
        return 0.0
    try:
        # Accept the trailing-Z UTC shape gh emits.
        ts = created.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(ts)
    except (ValueError, AttributeError):
        return 0.0
    now = datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    delta = (now - dt).total_seconds() / 86400.0
    return max(0.0, delta)


def _computed_score(item, fanout_counts):
    """The loop's own priority score in [0, 1] (issue #441) — a weighted sum
    of deterministic, observable signals. Higher = dispatch sooner. Computed
    in this script (script-tier), never by LLM inference."""
    filer = _FILER_VALUE.get(item.get("priority", ""), 0.0)

    fanout = fanout_counts.get(item.get("issue"), 0)
    fanout_norm = min(fanout, _FANOUT_CAP) / float(_FANOUT_CAP)

    # Scope size: smaller is a boost. 1 feature -> 1.0; saturates downward.
    n_feat = max(1, _feature_count_for_score(item))
    scope_norm = 1.0 / float(n_feat)

    bug_norm = 1.0 if item.get("issue_type") == "bug" else 0.0

    age_norm = min(_age_days(item), _AGE_CAP_DAYS) / _AGE_CAP_DAYS

    score = (
        _W_FILER * filer
        + _W_FANOUT * fanout_norm
        + _W_SCOPE * scope_norm
        + _W_BUG * bug_norm
        + _W_AGE * age_norm
    )
    # Clamp into [0, 1] (the weights sum to 0.65; clamping is defensive).
    return max(0.0, min(1.0, score))


# Score-tier quantization for the sort key. Quantizing the score to a fixed
# grid makes "all signals equal" produce an EXACT tie that falls back
# deterministically to the contract-touch barrier then issue number (issue
# #441 acceptance: equal signals → filer label (already in the score) → issue
# #), and keeps the contract barrier meaningful within a score tier.
_SCORE_QUANTUM = 1e-9


def _sort_key(item, fanout_counts):
    """Composite dispatch-ordering key (issue #441, refining #479):
    (-computed_score, contract_touch_rank, issue_number).

    The loop-computed score is PRIMARY (descending — higher score dispatches
    first). The contract-touch barrier is the SECONDARY tiebreak (True->0,
    False->1) so contract items lead WITHIN a score tier but never override a
    higher-scoring item across tiers (preserving Inv 26 grouping correctness).
    Issue number is the final stable tiebreak (asc). The filer `priority:`
    label is folded into the score as one weighted input, not consulted
    separately."""
    score = _computed_score(item, fanout_counts)
    contract_rank = 0 if item.get("contract_touch") else 1
    # Negate the score for ascending sort (higher score first). Round to the
    # quantum so floating-point noise never reorders an intended tie.
    return (-round(score / _SCORE_QUANTUM), contract_rank, item.get("issue", 0))


def _positive_int(value):
    """argparse type: integer >= 1."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"value must be an integer, got {value!r}"
        )
    if n < 1:
        raise argparse.ArgumentTypeError(
            f"value must be >= 1, got {n}"
        )
    return n


# The three code-producing dispatch shapes (Inv 26). The struck shape 2
# ("sequential-with-override") is intentionally NOT in this set: bounded
# scope is a hard constraint, not waivable by autonomy (maintainer policy on
# issue #435), so plan-batch.py never emits a session-override shape.
SHAPE_PARALLEL = "parallel-per-feature"
SHAPE_BARRIER = "multi-subagent-barrier"
SHAPE_DECOMPOSITION = "decomposition"
# The 4th dispatch shape (Inv 27, issue #478): research/investigation items
# produce FINDINGS, not code. They are routed to a read-only research
# subagent, never into the conflict-graph parallel-dispatch grouping.
SHAPE_RESEARCH = "research"


def _feature_count(item):
    """Distinct feature dirs an item touches. Prefers the `features` list
    emitted by triage-issue.py (Inv 26); falls back to 1 for the single
    `feature` label when `features` is absent (pre-#435 triage objects)."""
    feats = item.get("features")
    if isinstance(feats, list) and feats:
        return len(feats)
    return 1


def _dispatch_shape(item, decompose_threshold):
    """Stage-2 per-item shape: FIRST fitting shape in preference order.

    >= threshold features -> decomposition
    > 1 feature           -> multi-subagent-barrier
    exactly 1 feature     -> parallel-per-feature (performance preference)

    Cross-scope override (Inv 51 / issue #433): an item triage flagged
    `cross_scope: true` (its BODY spans multiple feature dirs — a repo-wide
    sweep / cross-feature rename) is NEVER shaped parallel-per-feature, even
    when its single `feature:` LABEL gives it a feature count of 1. A bounded
    per-feature subagent cannot write across features, so the body-derived
    cross_scope signal forces the barrier/decomposition lane: decomposition at/
    above the threshold, else multi-subagent-barrier. Bounded scope itself is
    unchanged — the fix is routing, not widening subagent scope.

    Cross-scope authority (Inv 51(a.2) / issue #669): the body-derived
    `cross_scope` signal is the AUTHORITATIVE multi-feature gate when present.
    triage-issue.py counts only EDIT-PATH references for `cross_scope` (bare
    feature-NAME mentions in prose are excluded), but the `features` list still
    carries those bare names for visibility (Inv 26 / #443). So an item with an
    EXPLICIT `cross_scope: false` is single-scope work — the labelled feature is
    the only edit target — and is shaped parallel-per-feature even when its
    `features` count is inflated by bare-name mentions. Only when `cross_scope`
    is ABSENT (legacy pre-#433 records) does the raw `features` count drive the
    multi-feature lane.
    """
    n = _feature_count(item)
    if item.get("cross_scope") is False:
        return SHAPE_PARALLEL
    if n >= decompose_threshold:
        return SHAPE_DECOMPOSITION
    if n > 1 or item.get("cross_scope"):
        return SHAPE_BARRIER
    return SHAPE_PARALLEL


def plan(items, max_parallel, decompose_threshold):
    """Run Stage 1 + Stage 2 + the priority-primary grouping; return the
    plan dict."""
    # Drop items whose decision is neither "work" nor "research" (per Inv 4 +
    # Inv 18: plan-batch accepts unfiltered triage arrays from
    # triage-batch.py; only dispatchable items are kept). Items without a
    # `decision` field are treated as "work" (backwards-compat with
    # pre-Inv-18 callers that pre-filter).
    items = [i for i in items
             if i.get("decision", "work") in ("work", "research")]

    # Exclude recorded DECOMPOSITION PARENTS (issue #948). triage-issue.py
    # flags an OPEN issue that is a parent of GitHub-native sub-issues
    # (`sub_issues_summary.total > 0`) OR a key in the `decomposition_parents`
    # state map (coexistence fallback) with `decomposition_parent: true`. Such
    # an item carries no own code change and converges via child rollup (closed
    # by close-decomposed-parents.py once all children close, Inv 53), never via
    # dispatch — so it must NEVER reach a TDD subagent. Filtering it here drops
    # it from selection_order, dispatch_shapes, and cross_scope_items in one
    # place. This does NOT violate the convergence guarantee (Inv 25): the
    # parent stays OPEN and tracked-by-decomposition, an existing non-work
    # tracked outcome. A child (it has a PARENT link but no children of its own,
    # so `decomposition_parent` is false) is NOT filtered and is dispatched
    # normally.
    items = [i for i in items if not i.get("decomposition_parent")]

    # Exclude NATIVELY-BLOCKED items (issue #970, Inv 62). triage-issue.py rule 5
    # populates a non-empty `blocked_by` (the OPEN native blocker numbers from
    # `gh api .../dependencies/blocked_by`, the authoritative blocked source,
    # Inv 59) ONLY on a blocked verdict — `reason_code == "blocked"`. The plain
    # blocked verdict (`decision=defer`/`blocked`) is already dropped by the
    # decision filter above; the #970 LEAK is the force-promoted case:
    # triage-batch.py's anti-infinite-defer counter (Inv 18) flips a
    # repeatedly-deferred blocked item to `decision=work` with
    # `reason_code="defer-limit-reached"`, which lifts the defer verdict but does
    # NOT clear the open native blocker, so the decision-only drop lets it
    # through. An item is natively blocked iff it carries a non-empty `blocked_by`
    # AND a blocked-origin `reason_code` ("blocked" or "defer-limit-reached"); it
    # is filtered here — at the same point as the Inv 58 parent filter — out of
    # selection_order, dispatch_shapes, and cross_scope_items, regardless of how
    # `decision` reads. This does NOT violate the convergence guarantee (Inv 25):
    # the item stays OPEN and tracked-by-dependency and re-enters the plan once
    # its blocker closes. An unblocked item is unaffected; a `blocked_by` carried
    # purely as a cross-item blocking-fanout signal on an actionable item (issue
    # #441) does not match the blocked-origin reason_code and is NOT filtered.
    _BLOCKED_REASONS = ("blocked", "defer-limit-reached")
    items = [i for i in items
             if not (i.get("blocked_by")
                     and i.get("reason_code") in _BLOCKED_REASONS)]

    # Loop-computed priority score (issue #441). Blocking-fanout is a
    # cross-item signal, so it is computed once over the whole dispatchable
    # batch before sorting. The per-item score then folds in the filer label,
    # scope size, bug-vs-enhancement, and age signals.
    fanout_counts = _fanout_counts(items)
    computed_scores = {
        str(i["issue"]): round(_computed_score(i, fanout_counts), 6)
        for i in items
    }

    # Stage 1 — work selection (dispatch-shape BLIND): composite key
    # (computed_score desc, contract_touch desc, issue asc), over dispatchable
    # items (Inv 26 (a) + issue #441 refining #479). The loop's own computed
    # score is PRIMARY; the contract-touch barrier is the SECONDARY tiebreak
    # (a barrier/conflict property, not a shape), and issue number is the final
    # tiebreak. The SAME sorted order drives barrier_first below, so the two
    # always agree. Research items participate in selection_order by the same
    # composite key (Inv 27 / issue #478).
    selection = sorted(items, key=lambda it: _sort_key(it, fanout_counts))
    selection_order = [i["issue"] for i in selection]

    # Stage 2 — per-item dispatch shape (item-shaped, Inv 26 (b) + Inv 27).
    # A research item gets the SHAPE_RESEARCH shape regardless of feature
    # count (findings, not code).
    dispatch_shapes = {}
    # Self-modifying-migration classification (the self-modifying-migration
    # invariant). Per code-producing work item, detect whether it migrates
    # loop-critical runtime state and tag the safe-execution pattern. Items
    # whose pattern is restart-safe are listed under `restart_needed` — the
    # tick driver, NOT this pure processor, sets the
    # .rabbit-auto-evolve-restart-needed marker for them and ends the tick
    # cleanly (the loop NEVER stops to ask a human).
    self_modifying_migrations = {}
    restart_needed = []
    # Cross-scope items (Inv 51 / issue #433): code-producing work items triage
    # flagged `cross_scope: true` (their BODY spans multiple feature dirs). They
    # are surfaced distinctly so the dispatcher/human sees which items need the
    # barrier/decomposition path rather than ordinary parallel single-feature
    # dispatch. Research items are excluded (they produce findings, not code).
    cross_scope_items = []
    for i in selection:
        if i.get("decision") == "research":
            dispatch_shapes[str(i["issue"])] = SHAPE_RESEARCH
            continue
        dispatch_shapes[str(i["issue"])] = _dispatch_shape(
            i, decompose_threshold)
        if i.get("cross_scope"):
            cross_scope_items.append(i["issue"])
        pattern = _self_modifying_pattern(i)
        if pattern is not None:
            self_modifying_migrations[str(i["issue"])] = pattern
            if pattern == PATTERN_RESTART_SAFE:
                restart_needed.append(i["issue"])

    # Research items (Inv 27 / issue #478) are routed to the read-only
    # research shape: they appear in selection_order and research_items but
    # NEVER in barrier_first or the conflict-graph groups (findings edit no
    # code, so the same-feature conflict edges and the contract-touch barrier
    # do not apply). Partition them out before the grouping.
    research_items = sorted(
        i["issue"] for i in selection if i.get("decision") == "research"
    )
    selection = [i for i in selection if i.get("decision") != "research"]

    # Step 1/2: priority-primary, barrier-secondary partition (issue #479).
    # barrier_first is the LEADING run of contract_touch items in the
    # composite-key order; the remainder is everything from the first
    # non-contract item onward (still in composite-key order). A critical
    # non-contract item at the front leaves barrier_first empty.
    first_non_contract = next(
        (idx for idx, it in enumerate(selection)
         if not it.get("contract_touch")),
        len(selection),
    )
    barrier_items = selection[:first_non_contract]
    barrier_first = [i["issue"] for i in barrier_items]

    # Step 3/4: greedy graph color the remainder (edge iff same feature).
    remainder = selection[first_non_contract:]
    color_features = []  # list[set[feature]] — index == color index
    color_items = []     # list[list[int]]   — index == color index

    for item in remainder:
        feat = item.get("feature")
        assigned = False
        for c in range(len(color_features)):
            if feat not in color_features[c]:
                color_features[c].add(feat)
                color_items[c].append(item["issue"])
                assigned = True
                break
        if not assigned:
            color_features.append({feat})
            color_items.append([item["issue"]])

    # Step 5: cap split — sub-groups of size <= max_parallel.
    groups = []
    for ci in color_items:
        for i in range(0, len(ci), max_parallel):
            groups.append(ci[i:i + max_parallel])

    return {
        "selection_order": selection_order,
        "dispatch_shapes": dispatch_shapes,
        # Loop-computed priority score per selected item (issue #441) — the
        # transparency surface. Keyed by issue-number string -> score in
        # [0, 1]. Emitted alongside the filer `priority` so the loop's
        # judgment is observable (filer label vs computed score side-by-side
        # downstream in status / tick-log).
        "computed_scores": computed_scores,
        "barrier_first": barrier_first,
        "groups": groups,
        "research_items": research_items,
        # Cross-scope work items (Inv 51 / issue #433), sorted ascending —
        # always present (empty when none). The dispatcher routes these to the
        # multi-subagent-barrier / decomposition path, never parallel
        # single-feature dispatch.
        "cross_scope_items": sorted(cross_scope_items),
        "self_modifying_migrations": self_modifying_migrations,
        "restart_needed": sorted(restart_needed),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic dispatch planner: reads triage JSON on "
                    "stdin, emits selection_order (Stage 1, shape-blind), "
                    "dispatch_shapes (Stage 2, per-item), and a barrier_first "
                    "+ groups plan on stdout. Contract-touch issues are "
                    "isolated; same-feature issues never share a group; group "
                    "size is capped by --max-parallel."
    )
    parser.add_argument(
        "--max-parallel", type=_positive_int, default=4,
        help="Maximum group size (default: 4). Must be an integer >= 1.",
    )
    parser.add_argument(
        "--decompose-threshold", type=_positive_int, default=10,
        help="Distinct-feature count at/above which an item's dispatch shape "
             "is 'decomposition' (default: 10). Must be an integer >= 1.",
    )
    args = parser.parse_args()

    raw = sys.stdin.read()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"plan-batch: malformed stdin JSON: {e}\n")
        sys.exit(1)
    if not isinstance(items, list):
        sys.stderr.write(
            f"plan-batch: stdin must be a JSON array, got "
            f"{type(items).__name__}\n"
        )
        sys.exit(1)

    result = plan(items, args.max_parallel, args.decompose_threshold)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
