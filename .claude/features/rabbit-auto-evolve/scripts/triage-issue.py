#!/usr/bin/env python3
"""triage-issue.py — classify a single rabbit-managed issue (Inv 3).

Per rabbit-auto-evolve spec.md Inv 3, emits a JSON object on stdout with
fields: issue, decision, reason_code, rationale, feature, features,
cross_scope, cross_scope_features, decomposition_parent, contract_touch,
priority, issue_type, created_at, blocked_by, planning_note. The
`decomposition_parent` boolean (Inv 58 / issue #948) is True when this OPEN
issue is a recorded decomposition parent — it HAS GitHub-native sub-issues
(`gh api repos/{slug}/issues/<n>` -> `sub_issues_summary.total > 0`) OR is a
key in the `decomposition_parents` state map (coexistence fallback); it tells
plan-batch.py to EXCLUDE the item from the dispatchable plan, since a
decomposition parent carries no own code change and converges via child rollup
(Inv 53), never via dispatch. The `cross_scope` boolean (Inv 51 /
issue #433) is True when the issue body implicates more than one feature
EDIT-PATH (the label PLUS body `.claude/features/<name>/` PATH references span
>= 2 dirs; bare feature-NAME mentions in prose are EXCLUDED per Inv 51(a.2) /
issue #669, and READ-ONLY "verify against <path>" path mentions are EXCLUDED
per issue #797) OR a cross-scope phrase ("repo-wide", "across all features",
"rename across", ...) OR an explicit cross-feature DECLARATION ("Cross-feature
(A + B)", "spans <feature> and <feature>"; issue #797) appears OUTSIDE a
parent-reference line; it routes a
body-spanning sweep to plan-batch.py's barrier/decomposition lane instead of
ordinary parallel-per-feature single-feature work. The parent-reference
exclusion (Inv 51(a.1) / issue #667) drops parent-pointer lines ("Sub-issue of
parent #N", "part of #N", ...) before the phrase check so a single-feature
decomposition sub-issue that merely QUOTES its parent's "repo-wide" framing is
not mis-flagged. `cross_scope_features` echoes the broader Inv 26 `features`
set (which still includes bare-name mentions for Stage-2 dispatch shaping).
The `issue_type` (bug/enhancement, from the GH label) and `created_at` (the
issue's ISO-8601 UTC creation timestamp) fields (issue #606 / Inv 44) feed
the bug-vs-enhancement and age signals of plan-batch.py's _computed_score
(Inv 44); without them both signals silently contribute 0. The `priority` field
(issue #484) echoes the issue's priority:<level> label value (None when
absent); plan-batch.py folds it into the loop's computed priority score as
ONE weighted input among several (Inv 44 / issue #441, refining the
priority-primary key of Inv 4 / issue #479). The `features` field (Inv 26 /
issue #435, #443) is the distinct set of feature directories the item
touches — the union of the feature:<name> label, every
`.claude/features/<name>/` body path, and every canonical feature name
(discovered by listing .claude/features/) matched word-for-word in the
body/title (bare-name detection, issue #443). It is the basis plan-batch.py
uses to choose a per-item dispatch shape.
Implements the seven-rule decision table
(top-down, first match wins); any ambiguity defaults to decision=defer,
reason_code=needs-judgment (never silently to work).

The decision set is exactly {work, defer, close-not-planned, research}
(issue #423 Part A; `research` added by issue #478). `close-completed` is
NEVER emittable from triage — a completed
closure can only be claimed once work has actually landed (the merge
phase's job via item-status.py, not triage's). Every `defer` and every
`research` decision carries a non-empty `planning_note` (for defer: what
analysis would unblock dispatch; for research: what to investigate and
report); the `work` and `close-not-planned` decisions carry
`planning_note: null`. A research/investigation item ("study X",
"evaluate Y") asks for FINDINGS, not code — see `_is_research`.

Read surface (strictly bounded):
  - Issue metadata via `gh issue view <N> --json
    number,title,body,labels,state,stateReason,comments,createdAt`. The
    `createdAt` timestamp (issue #606) is read in this SAME single call (no
    extra gh round-trip) to feed the age signal of the computed score (Inv
    46). The full comment
    thread and the state reason are read so rule 7 can reconcile a
    correction comment / conflicting retitle that supersedes the original
    body (issue #463): the most recent coherent intent is authoritative; a
    genuinely ambiguous conflict defers for maintainer clarification.
  - The named feature's spec head matter (frontmatter + first section) —
    for rule 6 only. The path is resolved dual-read (issue #399): the new
    specs/spec.md layout is preferred, with the legacy docs/spec/spec.md
    accepted as a fallback during the coexistence window.
  - The named feature's feature.json — for rule 4 (status field).
  - The last-30-days closed-issue list via `gh issue list --state closed
    --search "closed:>=<iso-date>"` — for rule 3.

No filesystem mutations. No reads outside the above surface.

Repo discovery uses rabbit-issue/_gh.repo_slug (sys.path bridge, same
pattern as fetch-queue.py).

Exit code: 0 on successful classification (any decision); non-zero on gh
failure or other unexpected error (stderr passthrough).

Version: 1.12.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path


# Add rabbit-issue/scripts to sys.path so `from _gh import repo_slug` works.
_HERE = Path(__file__).resolve().parent
_RABBIT_ISSUE_SCRIPTS = _HERE.parent.parent / "rabbit-issue" / "scripts"
if str(_RABBIT_ISSUE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RABBIT_ISSUE_SCRIPTS))
from _gh import repo_slug  # noqa: E402


# Prefix tokens commonly used in issue titles that should be stripped to
# isolate the "content-word tail" for rule-6 substring matching.
_PREFIX_DROP = re.compile(
    r"^\s*("
    r"please\s+"
    r"|add\s+"
    r"|implement\s+"
    r"|support\s+"
    r"|fix\s+"
    r"|feat(?:ure)?:\s*"
    r"|bug:\s*"
    r"|chore:\s*"
    r"|phase\s+\w+\s+task\s+\w+\s*:?\s*"
    r"|\w[\w-]*:\s*"  # generic "prefix: " (e.g., "my-feature: ...")
    r")+",
    re.IGNORECASE,
)


def _label_value(labels, prefix):
    """Return the suffix of the first label that starts with `prefix:`,
    else None."""
    for lbl in labels:
        name = lbl.get("name", "")
        if name.startswith(prefix + ":"):
            return name.split(":", 1)[1]
    return None


def _issue_type(labels):
    """Derive the bug-vs-enhancement issue type from the GH labels (issue
    #606 / Inv 44). Returns "bug" when a `bug` label is present, else
    "enhancement" when an `enhancement` label is present, else None. A `bug`
    label WINS when both are present (the higher-urgency signal).

    plan-batch.py's _computed_score fires the bug signal (1.0) exactly when
    the emitted `issue_type` equals "bug"."""
    names = {lbl.get("name", "") for lbl in labels}
    if "bug" in names:
        return "bug"
    if "enhancement" in names:
        return "enhancement"
    return None


def _gh_issue_view(num, fields):
    """Subprocess `gh issue view N -R <repo> --json <fields>`. Returns
    parsed JSON dict. Raises CalledProcessError on gh failure."""
    proc = subprocess.run(
        ["gh", "issue", "view", str(num),
         "--repo", repo_slug(),
         "--json", fields],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def _native_sub_issue_total(num):
    """Return the issue's GitHub-native sub-issue rollup total, read from
    `gh api repos/{slug}/issues/<num>` -> `sub_issues_summary.total` (issue
    #948). A `total > 0` means the issue HAS children — it is a parent of
    sub-issues, i.e. a decomposition parent. Reuses the same native-rollup
    access pattern close-decomposed-parents.py added in #940. Any read failure
    / unexpected payload returns 0 (treated as "no native sub-issues"), so a
    transient gh error never mis-flags a non-parent as a parent."""
    try:
        proc = subprocess.run(
            ["gh", "api", "repos/{}/issues/{}".format(repo_slug(), num)],
            capture_output=True, text=True,
        )
    except OSError:
        return 0
    if proc.returncode != 0:
        return 0
    try:
        payload = json.loads(proc.stdout or "")
    except ValueError:
        return 0
    summary = payload.get("sub_issues_summary") or {}
    try:
        return int(summary.get("total", 0))
    except (TypeError, ValueError):
        return 0


def _state_decomposition_parents():
    """Return the set of parent-issue numbers recorded in the
    `decomposition_parents` map of <state_dir>/auto-evolve-state.json (issue
    #948), the COEXISTENCE fallback source. The state dir resolves via
    RABBIT_AUTO_EVOLVE_STATE_DIR (the test seam shared with the sibling phase
    scripts) else <cwd>/.rabbit. Best-effort: any read/parse failure or a
    missing file yields an empty set (no fallback exclusions)."""
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    state_dir = override if override else os.path.join(os.getcwd(), ".rabbit")
    path = os.path.join(state_dir, "auto-evolve-state.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    dp = data.get("decomposition_parents") if isinstance(data, dict) else None
    if not isinstance(dp, dict):
        return set()
    parents = set()
    for key in dp:
        try:
            parents.add(int(key))
        except (TypeError, ValueError):
            continue
    return parents


def _is_decomposition_parent(issue_num, state_parents):
    """True iff the OPEN issue is a recorded decomposition parent (issue #948)
    and so must be EXCLUDED from the dispatchable plan — it carries no own code
    change and converges via child rollup (closed by close-decomposed-parents.py
    once all children close, Inv 53), never via dispatch.

    Detection aligns with #940's authoritative source:
      - PRIMARY: the GitHub-native sub-issue rollup shows the issue HAS children
        (`sub_issues_summary.total > 0`); OR
      - COEXISTENCE fallback: the issue is a key in the `decomposition_parents`
        state map (honored during the same coexistence window #940 established;
        deprecation criterion: drop the map-based fallback once no open parent
        carries a `decomposition_parents` entry).

    A child sub-issue (it has a PARENT link but no children of its own, so
    `total == 0` and it is not a map KEY) is NOT a decomposition parent and is
    still dispatched normally."""
    if issue_num in state_parents:
        return True
    return _native_sub_issue_total(issue_num) > 0


def _gh_issue_list_closed_last_30():
    """List closed issues whose `closed:` date is within the last 30 days."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).date()
    proc = subprocess.run(
        ["gh", "issue", "list",
         "--repo", repo_slug(),
         "--state", "closed",
         "--search", f"closed:>={cutoff.isoformat()}",
         "--json", "number,title",
         "--limit", "100"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def resolve_spec_path(feature_root, name):
    """Resolve a feature spec/contract doc path, dual-read (issue #399).

    Prefers the new layout <feature_root>/specs/<name>; falls back to the
    legacy <feature_root>/docs/spec/<name>. During the docs/spec/ -> specs/
    coexistence window both layouts resolve; the fallback is dropped once
    every feature has migrated. `name` is a leaf filename such as "spec.md".
    When neither layout exists the legacy docs/spec/ candidate is returned so
    downstream existence checks report the canonical legacy path.

    Accepts either a str or a pathlib.Path for `feature_root`; always returns
    a pathlib.Path.
    """
    root = Path(feature_root)
    preferred = root / "specs" / name
    if preferred.is_file():
        return preferred
    return root / "docs" / "spec" / name


def _read_spec_head_matter(feature_dir):
    """Read the first ~4KB of the feature's spec.md (frontmatter + first
    section) for rule-6 matching. The path is resolved dual-read (specs/
    preferred, docs/spec/ fallback). Returns "" if absent."""
    spec_path = resolve_spec_path(feature_dir, "spec.md")
    if not spec_path.is_file():
        return ""
    try:
        with spec_path.open("r", encoding="utf-8") as f:
            return f.read(4096)
    except OSError:
        return ""


def _read_feature_status(feature_dir):
    """Return feature.json's `status` field, or None on any read/parse
    failure (caller treats absence as not-retired)."""
    fjson = feature_dir / "feature.json"
    if not fjson.is_file():
        return None
    try:
        with fjson.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("status")
    except (OSError, json.JSONDecodeError):
        return None


def _title_tail(title):
    """Strip common prefix tokens to isolate the content-word tail."""
    return _PREFIX_DROP.sub("", title).strip().lower()


def _contract_touch(labels, body):
    """contract_touch is true iff feature:contract label OR body literally
    declares any path under .claude/features/contract/."""
    if _label_value(labels, "feature") == "contract":
        return True
    if ".claude/features/contract/" in (body or ""):
        return True
    return False


# Match `.claude/features/<name>/` path references in an issue body. The
# captured group is the feature-directory name (the second path segment).
_FEATURE_PATH = re.compile(r"\.claude/features/([A-Za-z0-9._-]+)/")

# Subdirectories under .claude/features/ that are NOT dispatchable feature
# scopes (policy text, the contract feature is its own scope, the README).
# `contract` IS a real feature dir, so it is kept; only non-feature entries
# are excluded from the canonical bare-name vocabulary.
_NON_FEATURE_DIRS = frozenset({"policy", "README.md"})


def _discover_feature_names(repo_root):
    """Canonical feature-name set, discovered by listing .claude/features/.

    Stage-2 bare-name detection (issue #443) scans the issue body/title for
    these names, so the vocabulary is read dynamically at triage time rather
    than hardcoded — a new feature dir is picked up with no code change.
    Returns the set of immediate subdirectory names under
    <repo_root>/.claude/features/ that carry a feature.json (i.e. real
    feature scopes), excluding non-feature entries like `policy`. Returns an
    empty set when the directory is unreadable.
    """
    features_dir = Path(repo_root) / ".claude" / "features"
    names = set()
    try:
        for entry in features_dir.iterdir():
            if not entry.is_dir():
                continue
            if entry.name in _NON_FEATURE_DIRS:
                continue
            if (entry / "feature.json").is_file():
                names.add(entry.name)
    except OSError:
        return set()
    return names


def _bare_name_matches(text, feature_names):
    """Feature names appearing as a whole word in `text` (issue #443).

    Uses a word-boundary match (`\\b<name>\\b`) so a name is only detected
    when it stands alone — `rabbit-meta` matches "touches rabbit-meta," but
    NOT the longer token "rabbit-metadata-store". Returns the matching subset
    of `feature_names`.
    """
    if not text or not feature_names:
        return set()
    matched = set()
    for name in feature_names:
        if re.search(r"\b" + re.escape(name) + r"\b", text):
            matched.add(name)
    return matched


def _feature_set(feature_label, body, title="", feature_names=None):
    """Distinct feature directories an issue touches (Stage-2 basis, Inv 26).

    The set is the union of THREE detection methods (issue #435, #443):
      (a) the feature:<name> label;
      (b) every `.claude/features/<name>/` path literally referenced in the
          body; and
      (c) every canonical feature name (from `feature_names`, discovered by
          listing .claude/features/) that appears as a whole word in the body
          OR title — catching features named by bare name in prose or a
          markdown table with no full path (issue #443).
    Returned sorted for deterministic output. Used by plan-batch.py to choose
    a dispatch shape per item:
      1 feature       -> parallel-per-feature
      >1, < threshold -> multi-subagent-barrier
      >= threshold    -> decomposition
    """
    feats = set()
    if feature_label:
        feats.add(feature_label)
    for m in _FEATURE_PATH.findall(body or ""):
        feats.add(m)
    if feature_names:
        feats |= _bare_name_matches(f"{title or ''}\n{body or ''}",
                                    feature_names)
    return sorted(feats)


# Cross-scope detection (Inv 51 / issue #433) -------------------------------
# An issue whose BODY spans multiple feature directories is a cross-scope item:
# a single bounded per-feature TDD subagent (one .rabbit-scope-active-<feature>)
# cannot write outside its one feature, so plan-batch.py MUST route it to the
# barrier/decomposition lane instead of ordinary parallel-per-feature work. We
# emit a `cross_scope` boolean (and `cross_scope_features`) so the body-derived
# signal is an additional input to Stage-2 shaping even when the single
# feature: LABEL would otherwise mislead the planner.
#
# Cross-scope phrases that imply a repo-wide / multi-feature sweep regardless
# of how many feature dirs the body literally names (whole-phrase,
# case-insensitive).
_CROSS_SCOPE_PHRASE = re.compile(
    r"repo-wide"
    r"|every feature"
    r"|across all features"
    r"|across every feature"
    r"|all features"
    r"|rename across",
    re.IGNORECASE,
)

# Parent-reference lines (Inv 51(a.1) / issue #667). A shape-3 decomposition
# sub-issue is scoped to ONE feature but typically QUOTES its parent's framing
# on a parent-pointer line (e.g. "Sub-issue of parent #420 (retire B/B
# terminology repo-wide)"). A cross-scope phrase quoted on such a line describes
# the PARENT's scope, not the sub-issue's own scope, so it must NOT contribute
# to the cross-scope PHRASE signal. We detect a parent-reference line by a
# parent-pointer phrasing anywhere on the line (whole-phrase, case-insensitive).
_PARENT_REF_LINE = re.compile(
    r"sub-?issue of"
    r"|child of\s+#\d+"
    r"|parent issue\s+#\d+"
    r"|parent\s+#\d+"
    r"|part of\s+#\d+"
    r"|decomposed from\s+#\d+"
    r"|split from\s+#\d+",
    re.IGNORECASE,
)


def _strip_parent_ref_lines(body):
    """Return `body` with every parent-reference line removed (Inv 51(a.1)).

    A line matching `_PARENT_REF_LINE` quotes the PARENT's framing, not the
    sub-issue's own scope, so it is dropped before the cross-scope PHRASE signal
    is evaluated.
    """
    lines = (body or "").splitlines()
    kept = [ln for ln in lines if not _PARENT_REF_LINE.search(ln)]
    return "\n".join(kept)


# Read-only path-reference lines (Inv 51(a.2) / issue #797). A
# `.claude/features/<name>/` path appearing on a line that carries a read-only
# verb names a CONFIRMATION target, not an EDIT target: the issue reads or
# verifies against that path but does NOT write under it (e.g. "verify against
# .claude/features/contract/lib/runtime.py that the migration landed"). Such a
# path must NOT inflate the cross-scope EDIT-PATH count, so it is stripped
# before the edit-target feature set is computed. Detected by a read-only verb
# anywhere on the line (whole-phrase, case-insensitive).
_READONLY_PATH_LINE = re.compile(
    r"verify against"
    r"|confirm against"
    r"|read-only"
    r"|do not edit"
    r"|don't edit"
    r"|refer to"
    r"|\bsee\b",
    re.IGNORECASE,
)


def _strip_readonly_path_lines(body):
    """Return `body` with every read-only path-reference line removed (Inv
    51(a.2) / issue #797).

    A line matching `_READONLY_PATH_LINE` names a read-only confirmation target,
    not an edit target, so any `.claude/features/<name>/` path on it is dropped
    before the cross-scope EDIT-PATH feature set is computed.
    """
    lines = (body or "").splitlines()
    kept = [ln for ln in lines if not _READONLY_PATH_LINE.search(ln)]
    return "\n".join(kept)


# Explicit cross-feature scope DECLARATIONS (Inv 51(b) / issue #797). A body
# may declare a cross-feature scope in prose without naming two
# `.claude/features/<name>/` edit-paths and without a repo-wide phrase — e.g. a
# `## Scope` heading reading "Cross-feature (rabbit-auto-evolve + contract)" or
# "Cross-feature: A, B", or a sentence "this work spans A and B". Such an
# explicit declaration MUST set cross_scope true (it was a false NEGATIVE
# before #797). Matched case-insensitive:
#   - "cross-feature" / "cross feature" followed (within a short window) by a
#     "<name> + <name>" or "<name>, <name>" enumeration; OR
#   - "spans <feature> and <feature>".
_CROSS_FEATURE_DECL = re.compile(
    r"cross[ -]feature\b[^\n]{0,40}?[\w.-]+\s*(?:\+|,|and)\s*[\w.-]+"
    r"|\bspans\s+[\w.-]+\s+and\s+[\w.-]+",
    re.IGNORECASE,
)


def _edit_target_features(feature_label, body):
    """EDIT-TARGET feature set for the cross-scope signal (Inv 51(a.2)).

    Counts ONLY feature references that denote an EDIT TARGET — the `feature:`
    label PLUS every distinct `.claude/features/<name>/` PATH literally
    referenced in the body (dirs the issue will actually write under). Bare
    feature-NAME mentions in descriptive prose (the Inv 26 method-(c) whole-word
    detection) are EXCLUDED: a phrase like "use rabbit-issue vocabulary" names a
    vocabulary, not an edit target, and MUST NOT inflate the cross-scope count
    (issue #669). READ-ONLY path references — a `.claude/features/<name>/` path
    on a line that carries a read-only verb ("verify against", "see", "refer
    to", "read-only", "confirm against", "do not edit") — are ALSO EXCLUDED
    (issue #797): a "verify against .claude/features/contract/lib/runtime.py"
    mention is a confirmation target, not an edit target, and MUST NOT inflate
    the cross-scope count. This is intentionally NARROWER than `_feature_set`,
    which keeps bare names for Stage-2 dispatch shaping.
    """
    feats = set()
    if feature_label:
        feats.add(feature_label)
    for m in _FEATURE_PATH.findall(_strip_readonly_path_lines(body)):
        feats.add(m)
    return feats


def _cross_scope(feature_label, title, body):
    """True iff the issue implicates more than one feature (Inv 51).

    Three independent signals (any suffices):
      (a) the EDIT-TARGET feature set (the label PLUS every distinct body
          `.claude/features/<name>/` PATH reference — dirs the issue will write
          under) spans >= 2 feature dirs (Inv 51(a.2) / issue #669, #797); OR
      (b) an explicit cross-scope phrase (repo-wide, across all features,
          rename across, ...) appears in the title OR in the body OUTSIDE any
          parent-reference line (Inv 51(a.1) / issue #667); OR
      (c) an explicit cross-feature scope DECLARATION ("Cross-feature (A + B)",
          "Cross-feature: A, B", "spans <feature> and <feature>") appears in the
          title OR body OUTSIDE any parent-reference line (Inv 51(b) / #797).

    Signal (a) counts EDIT-PATH references only — bare feature-NAME mentions in
    prose are excluded (issue #669) and READ-ONLY path references on a "verify
    against <path>" / "see <path>" line are excluded (issue #797), so a
    single-feature sub-issue whose text merely names or verifies-against another
    feature is NOT mis-flagged cross_scope. The phrase signal (b) and the
    declaration signal (c) exclude parent-reference lines so a sub-issue that
    merely QUOTES its parent's framing on a parent-pointer line is NOT
    mis-flagged (Inv 51(a.1) / issue #667). A body whose OWN scope enumerates
    >= 2 distinct feature EDIT-PATHS, or explicitly declares a cross-feature
    scope, still yields True.

    Default False when at most one edit-target feature dir is implicated and no
    cross-scope phrase or cross-feature declaration appears outside
    parent-reference lines.
    """
    if len(_edit_target_features(feature_label, body)) >= 2:
        return True
    own_scope_text = f"{title or ''}\n{_strip_parent_ref_lines(body)}"
    if _CROSS_SCOPE_PHRASE.search(own_scope_text):
        return True
    return bool(_CROSS_FEATURE_DECL.search(own_scope_text))


# Research/investigation classification (issue #478) ------------------------
# A research/spike item asks for FINDINGS or a RECOMMENDATION, not a behavior
# change. The loop's only code-producing shape is a TDD-cycle PR, so such an
# item has no dispatch home — before #478 it was wrongly closed not-planned
# (an Inv 25 convergence violation). Triage classifies it as
# decision=research so plan-batch can route it to the research shape (Inv 27).

# Research/investigation verbs (whole-word, case-insensitive). All three
# detection signals must hold (see _is_research) so a normal "implement X"
# item is never misrouted.
_RESEARCH_VERB = re.compile(
    r"\b(study|evaluate|investigate|survey|assess|recommend|compare|explore)"
    r"(?:s|d|ing|ed|ment|ation|ations)?\b",
    re.IGNORECASE,
)

# Findings/recommendation request signals — the body asks for an analysis or
# a recommendation rather than a behavior change (whole-word/phrase,
# case-insensitive).
_FINDINGS_REQUEST = re.compile(
    r"\b(findings?|recommendation|recommend|report|analysis|"
    r"evaluation|assessment|tradeoffs?|trade-offs?|options?|approaches?)\b",
    re.IGNORECASE,
)

# Imperative behavior-change phrasing that points at a concrete code change —
# its presence DISQUALIFIES the research classification (the item asks for
# code, not findings).
_CODE_CHANGE_PHRASE = re.compile(
    r"\b(implement|fix|add|refactor|rename|delete|remove|wire|patch|"
    r"migrate)\b",
    re.IGNORECASE,
)


def _is_research(title, body, feature_label):
    """True iff the issue is a research/investigation item (issue #478).

    ALL three signals must hold:
      1. a research verb appears in the title or body;
      2. no concrete code-change target — no `.claude/features/<name>/` path
         reference beyond the labelled feature dir, and no imperative
         implement/fix/add phrasing pointing at a behavior change;
      3. the body asks for a recommendation / findings / report / analysis.
    """
    text = f"{title or ''}\n{body or ''}"
    # Signal 1 — research verb present.
    if not _RESEARCH_VERB.search(text):
        return False
    # Signal 2 — no concrete code-change target.
    #   (a) no extra feature-dir path reference beyond the labelled one.
    body_feats = {m for m in _FEATURE_PATH.findall(body or "")}
    extra_feats = body_feats - ({feature_label} if feature_label else set())
    if extra_feats:
        return False
    #   (b) no imperative code-change phrasing.
    if _CODE_CHANGE_PHRASE.search(text):
        return False
    # Signal 3 — findings / recommendation requested.
    if not _FINDINGS_REQUEST.search(text):
        return False
    return True


# Match `blocked-by: #N` (case-insensitive). Captures the integer N. A real
# dependency declaration: it is honored anywhere in the body (the `#N` ref is
# unambiguous on its own).
_BLOCKED_BY_GOOD = re.compile(r"blocked-by:\s*#(\d+)", re.IGNORECASE)
# Match a STRUCTURAL blocked-by declaration: a line that STARTS with the
# `blocked-by:` token after only optional list/quote markers (`-`, `*`, `>`,
# whitespace). This is deliberately NOT a substring match (issue #941): a prose
# MENTION of the `blocked-by:` token mid-sentence (an issue describing or
# discussing the dependency mechanism in a sentence, code span, or table) does
# NOT declare an ordering dependency and must never trigger the malformed-defer.
# Only a line genuinely declaring a dependency in the structural position counts.
_BLOCKED_BY_STRUCTURAL = re.compile(
    r"^[ \t>*\-]*blocked-by:", re.IGNORECASE | re.MULTILINE)


def _declares_blocked_by(body):
    """True iff `body` STRUCTURALLY declares a blocked-by dependency (Inv 3
    rule 5, issue #941).

    A declaration is recognized only when the body carries the concrete
    `blocked-by: #N` form ANYWHERE, OR a line that STARTS with the
    `blocked-by:` token after only optional list/quote markers. A bare prose
    occurrence of the `blocked-by:` token mid-sentence is NOT a declaration and
    returns False, so it passes through as actionable rather than false-deferred.
    """
    text = body or ""
    if _BLOCKED_BY_GOOD.search(text):
        return True
    return bool(_BLOCKED_BY_STRUCTURAL.search(text))


# Supersession phrases (case-insensitive) that mark a comment as an
# authoritative correction of the original body (issue #463).
_SUPERSEDE_PHRASES = (
    "supersedes",
    "correction",
    "corrected proposal",
    "ignore the original",
    "revised scope",
    "original body was wrong",
)

# Match a target/path token: a `docs/...` or `specs/...` path, or any
# `.claude/features/<...>/` reference. Used to detect a title-vs-body
# target conflict (issue #463).
_TARGET_TOKEN = re.compile(
    r"(?:\.claude/features/[\w./{},-]+|specs/[\w./{},-]*|docs/[\w./{},-]*)"
)


def _comment_bodies(comments):
    """Return the list of comment body strings in chronological order
    (oldest first), skipping any malformed (non-dict / empty) entries."""
    bodies = []
    for c in comments or []:
        if isinstance(c, dict):
            b = c.get("body")
            if isinstance(b, str) and b.strip():
                bodies.append(b)
    return bodies


def _superseding_comment(comments):
    """Return the body of the MOST RECENT comment containing supersession
    language (issue #463), or None when no comment carries a correction."""
    found = None
    for body in _comment_bodies(comments):
        low = body.casefold()
        if any(p in low for p in _SUPERSEDE_PHRASES):
            found = body  # keep walking — most recent (last) wins
    return found


def _target_tokens(text):
    """Distinct target/path tokens in `text` (casefolded), order-preserved.

    Tokens are kept verbatim (the trailing `/` of a directory target like
    `specs/` is preserved) so the reconciliation planning_note names the
    target the way the maintainer wrote it."""
    seen = []
    for m in _TARGET_TOKEN.findall(text or ""):
        tok = m.casefold()
        if tok and tok not in seen:
            seen.append(tok)
    return seen


def _root_segment(token):
    """Top-level path segment of a target token (text before the first '/')."""
    return token.split("/", 1)[0]


def _title_body_target_conflict(title, body):
    """Return (title_target, body_target) when the title declares a target
    token absent from the body AND the body declares a distinct target token
    — i.e. title and body describe DIFFERENT targets (issue #463). Returns
    None when there is no such conflict.

    When the body declares multiple distinct targets, the body target whose
    ROOT path segment differs from the title's is preferred (the most
    distinctive divergence) — e.g. for a title under `docs/...` and a body
    naming both `docs/spec/` and `specs/`, the reported conflict is
    `specs/` (root `specs` ≠ `docs`), the genuinely divergent target.
    """
    title_targets = _target_tokens(title)
    body_targets = _target_tokens(body)
    if not title_targets or not body_targets:
        return None
    body_text = (body or "").casefold()
    title_text = (title or "").casefold()
    for tt in title_targets:
        if tt in body_text:
            continue
        candidates = [bt for bt in body_targets
                      if bt not in title_text and bt != tt]
        if not candidates:
            continue
        # Prefer a body target whose root segment differs from the title's.
        tt_root = _root_segment(tt)
        divergent = [bt for bt in candidates
                     if _root_segment(bt) != tt_root]
        chosen = divergent[0] if divergent else candidates[0]
        return (tt, chosen)
    return None


def _reconcile(base, title, body, state_reason, comments):
    """Comment-thread reconciliation (issue #463), applied to an otherwise
    actionable (rule-7 `work`) issue. Reads the full comment thread plus the
    state reason and the title/body targets and refines the verdict between
    `work` (corrected intent is coherent) and `defer` (genuinely ambiguous
    conflict). Returns the reconciled decision dict.
    """
    correction = _superseding_comment(comments)
    conflict = _title_body_target_conflict(title, body)
    reopened = (state_reason or "").casefold() == "reopened"
    has_comments = bool(_comment_bodies(comments))

    # An authoritative correction comment supersedes the original body: the
    # most recent coherent intent wins → dispatch the corrected work. This is
    # checked FIRST so a deliberate maintainer correction overrides a stale
    # research framing as much as a stale code-change framing (issue #463).
    if correction:
        return dict(base,
                    decision="work",
                    reason_code="actionable",
                    rationale="A correction comment supersedes the original "
                              "body; dispatching the most recent corrected "
                              "intent.")

    # Research/investigation classification (issue #478). When the issue asks
    # for FINDINGS or a RECOMMENDATION rather than a behavior change, route it
    # to the research dispatch shape (Inv 27) instead of a TDD-cycle PR.
    # Checked after the correction-comment case (so a deliberate correction
    # still wins) but before the work pass-through / conflict resolution.
    if _is_research(title, body, base.get("feature")):
        return dict(base,
                    decision="research",
                    reason_code="research",
                    rationale="Issue asks for findings/recommendation, not a "
                              "code change; routing to the research dispatch "
                              "shape.",
                    planning_note="Investigate and produce findings: " +
                                  (title.strip() if title and title.strip()
                                   else "see the issue body") +
                                  ". Commit findings under "
                                  "docs/findings/<issue-N>-<slug>.md and close "
                                  "the item completed referencing that commit.")

    # No detection signal → strict pre-#463 pass-through (no-regression).
    if not conflict and not (reopened and has_comments):
        return dict(base,
                    decision="work",
                    reason_code="actionable",
                    rationale="No earlier rule matched; issue is actionable.")

    # A reopened issue whose retitle conflicts with the body on the target,
    # with no coherent superseding comment to resolve it, is genuinely
    # ambiguous → defer for maintainer clarification.
    if conflict and reopened:
        title_t, body_t = conflict
        return dict(base,
                    decision="defer",
                    reason_code="needs-judgment",
                    rationale="Reopened issue's title and body conflict on the "
                              "target; correct intent is ambiguous.",
                    planning_note=f"Body and correction comment conflict on "
                                  f"target [{title_t} vs {body_t}]; need "
                                  f"maintainer clarification before dispatch.")

    # A title/body target conflict on a non-reopened issue: the title is the
    # most recent authored signal → the title wins, dispatch with a note.
    if conflict:
        title_t, body_t = conflict
        return dict(base,
                    decision="work",
                    reason_code="actionable",
                    rationale=f"Title and body conflict on target "
                              f"[{title_t} vs {body_t}]; the title is the most "
                              f"recent intent and wins.")

    # Reopened with comments but no parseable correction/conflict — fall
    # through to actionable (the comments may be discussion, not correction).
    return dict(base,
                decision="work",
                reason_code="actionable",
                rationale="No earlier rule matched; issue is actionable.")


def classify(issue_num, repo_root):
    """Run the seven-rule decision table. Returns a dict ready for json.dump."""
    # ---- Fetch issue metadata ----
    # `createdAt` is added to the SAME single gh call (issue #606) so the
    # age signal of plan-batch._computed_score (Inv 44) has data — no extra
    # gh round-trip.
    issue = _gh_issue_view(
        issue_num,
        "number,title,body,labels,state,stateReason,comments,createdAt",
    )

    title = issue.get("title", "") or ""
    body = issue.get("body", "") or ""
    labels = issue.get("labels", []) or []
    # Full comment thread + state reason — read so rule 7 can reconcile a
    # correction comment / retitle that supersedes the original body (#463).
    comments = issue.get("comments", []) or []
    state_reason = issue.get("stateReason", "") or ""

    feature_label = _label_value(labels, "feature")
    priority_label = _label_value(labels, "priority")
    # issue_type / created_at (issue #606 / Inv 44) feed plan-batch's
    # bug-vs-enhancement and age signals (Inv 44). Both are derived from the
    # SAME gh fetch above (labels + createdAt) — no extra gh call.
    issue_type = _issue_type(labels)
    created_at = issue.get("createdAt") or None
    ctouch = _contract_touch(labels, body)
    # Canonical feature vocabulary (discovered from .claude/features/) — the
    # basis for Stage-2 bare-name cross-feature detection (issue #443).
    feature_names = _discover_feature_names(repo_root)
    # Distinct feature set (Inv 26) computed once — reused for both `features`
    # and the cross-scope signal (Inv 51).
    features = _feature_set(feature_label, body, title, feature_names)
    # `cross_scope` (Inv 51 / issue #433): true when the issue body spans more
    # than one feature EDIT-PATH (label + body `.claude/features/<name>/` paths;
    # bare-name mentions excluded per Inv 51(a.2) / issue #669) OR carries a
    # cross-scope phrase. Drives plan-batch's body-derived routing so a
    # body-spanning sweep is shaped barrier/decomposition, never
    # parallel-per-feature, even when its single feature: LABEL would mislead
    # the planner.
    cross_scope = _cross_scope(feature_label, title, body)

    # `decomposition_parent` (issue #948): True when this OPEN issue is a
    # recorded decomposition parent — a parent of GitHub-native sub-issues
    # (`sub_issues_summary.total > 0`) OR a key in the `decomposition_parents`
    # state map (coexistence fallback). plan-batch.py EXCLUDES such an item from
    # the dispatchable plan: a decomposition parent carries no own code change
    # and converges via child rollup (Inv 53), never via dispatch. Computed once
    # here so the per-issue gh-api/state read does not leak into the pure-JSON
    # planner.
    decomposition_parent = _is_decomposition_parent(
        issue_num, _state_decomposition_parents())

    base = {
        "issue": issue_num,
        "feature": feature_label,
        # `features` is the distinct set of feature dirs the item touches —
        # the union of (a) the feature label, (b) `.claude/features/<name>/`
        # body path references, and (c) bare feature names matched word-for-
        # word in the body/title (issue #443). The Stage-2 dispatch-shape
        # basis (Inv 26 / issue #435). Always present; for a malformed-labels
        # issue with no body paths and no bare-name mention it is [].
        "features": features,
        # `cross_scope` (Inv 51 / issue #433) is True when the issue body
        # implicates more than one feature EDIT-PATH (the label + body
        # `.claude/features/<name>/` paths span >= 2 dirs; bare-name mentions
        # excluded per Inv 51(a.2) / issue #669) OR a cross-scope phrase
        # ("repo-wide", "across all features", ...) appears OUTSIDE a
        # parent-reference line (Inv 51(a.1) / issue #667). Always present on
        # EVERY decision; plan-batch.py routes a cross_scope item to
        # multi-subagent-barrier/decomposition, never parallel-per-feature.
        # `cross_scope_features` echoes the broader `features` set (with
        # bare-name mentions) so the dispatcher sees WHICH features it spans.
        "cross_scope": cross_scope,
        "cross_scope_features": features,
        # `decomposition_parent` (issue #948) is True when this OPEN issue is a
        # recorded decomposition parent — it HAS GitHub-native sub-issues
        # (`sub_issues_summary.total > 0`) OR is a key in the
        # `decomposition_parents` state map (coexistence fallback). Always
        # present on EVERY decision; plan-batch.py filters a
        # `decomposition_parent: true` item out of selection_order /
        # dispatch_shapes / cross_scope_items so the parent is never dispatched
        # to a TDD subagent (it converges via child rollup, Inv 53).
        "decomposition_parent": decomposition_parent,
        "contract_touch": ctouch,
        # `priority` (issue #484) echoes the issue's priority:<level> label
        # value (None when absent). plan-batch.py folds it into the loop's
        # computed priority score as ONE weighted input (Inv 44 / issue #441,
        # refining the priority-primary key of Inv 4 / issue #479); a None
        # filer label simply contributes nothing to the score.
        "priority": priority_label,
        # `issue_type` (issue #606 / Inv 44) is "bug"/"enhancement"/None,
        # derived from the GH bug/enhancement label (bug wins if both). It
        # drives the bug-vs-enhancement signal of plan-batch._computed_score
        # (Inv 44); a None type contributes nothing to the score.
        "issue_type": issue_type,
        # `created_at` (issue #606 / Inv 44) echoes the issue's ISO-8601 UTC
        # createdAt (trailing-Z shape), None when gh omits it. It drives the
        # age signal of plan-batch._computed_score (Inv 44); a None timestamp
        # contributes nothing (no crash — _age_days tolerates absence).
        "created_at": created_at,
        "blocked_by": [],
        # planning_note is null for non-defer decisions; each defer return
        # overrides it with a non-empty note (issue #423 Part A).
        "planning_note": None,
    }

    # ---- Rule 1: malformed-labels ----
    if not feature_label or not priority_label:
        return dict(base,
                    decision="defer",
                    reason_code="malformed-labels",
                    rationale="Issue is missing required feature: or priority: label.",
                    planning_note="Add the missing feature:<name> and/or "
                                  "priority:<level> label so the issue can be "
                                  "routed and scoped.")

    # ---- Rule 2: unknown-feature ----
    feature_dir = Path(repo_root) / ".claude" / "features" / feature_label
    if not feature_dir.is_dir():
        return dict(base,
                    decision="close-not-planned",
                    reason_code="unknown-feature",
                    rationale=f"feature:{feature_label} label has no matching feature directory.")

    # ---- Rule 3: duplicate (substring match against recently closed) ----
    try:
        closed = _gh_issue_list_closed_last_30()
    except subprocess.CalledProcessError:
        closed = None
    if closed is None:
        return dict(base,
                    decision="defer",
                    reason_code="needs-judgment",
                    rationale="Could not query closed-issue list for duplicate check.",
                    planning_note="Re-run triage once `gh issue list` is "
                                  "reachable to complete the duplicate check.")

    title_cf = title.casefold()
    for ci in closed:
        cti = (ci.get("title", "") or "").casefold()
        if title_cf and title_cf in cti:
            return dict(base,
                        decision="close-not-planned",
                        reason_code="duplicate",
                        rationale=f"Title is a case-folded substring match of closed issue #{ci.get('number')}.")

    # ---- Rule 4: feature-retired ----
    status = _read_feature_status(feature_dir)
    if status == "retired":
        return dict(base,
                    decision="close-not-planned",
                    reason_code="feature-retired",
                    rationale=f"Feature {feature_label} status is 'retired'.")

    # ---- Rule 5: blocked-by ----
    # Rule 5 fires only on a STRUCTURAL dependency declaration, never on a bare
    # prose mention of the `blocked-by:` token (issue #941): an issue that
    # merely describes/discusses the mechanism is NOT a dependency and passes
    # through as actionable.
    if _declares_blocked_by(body):
        matches = _BLOCKED_BY_GOOD.findall(body)
        if not matches:
            # Structurally declared but malformed (no valid #N) — ambiguity
            # default.
            return dict(base,
                        decision="defer",
                        reason_code="needs-judgment",
                        rationale="Body declares 'blocked-by:' but no integer issue reference found.",
                        planning_note="Clarify the blocked-by dependency: edit "
                                      "the body to cite a concrete `blocked-by: "
                                      "#N`, or remove the declaration if there "
                                      "is no real blocker.")
        blocked_open = []
        for n in matches:
            n_int = int(n)
            try:
                dep = _gh_issue_view(n_int, "number,state")
            except subprocess.CalledProcessError:
                return dict(base,
                            decision="defer",
                            reason_code="needs-judgment",
                            rationale=f"Could not query state of cited dependency #{n_int}.",
                            planning_note=f"Verify the state of cited "
                                          f"dependency #{n_int}; re-run triage "
                                          f"once it is reachable.")
            dep_state = (dep.get("state") or "").upper()
            if dep_state == "OPEN":
                blocked_open.append(n_int)
        if blocked_open:
            return dict(base,
                        decision="defer",
                        reason_code="blocked",
                        rationale=f"Blocked by still-open issue(s): {blocked_open}.",
                        blocked_by=blocked_open,
                        planning_note=f"Wait for blocking issue(s) "
                                      f"{blocked_open} to close, then re-triage; "
                                      f"dispatch is unblocked once they land.")

    # ---- Rule 6: already-spec'd ----
    head_matter = _read_spec_head_matter(feature_dir).casefold()
    tail = _title_tail(title)
    if tail and len(tail) >= 3 and tail in head_matter:
        return dict(base,
                    decision="close-not-planned",
                    reason_code="already-spec'd",
                    rationale="Spec head matter already documents this behavior (title-tail substring match).")

    # ---- Rule 7: actionable / work (with #463 comment-thread reconciliation) ----
    # The issue is structurally actionable; before returning `work`,
    # reconcile the full comment thread + state reason + title/body targets
    # so a correction comment or conflicting retitle that supersedes the
    # original body is honored (issue #463). Reconciliation only ever
    # refines between `work` and `defer` — it never overrides an earlier
    # close/blocked/malformed verdict.
    return _reconcile(base, title, body, state_reason, comments)


def main():
    parser = argparse.ArgumentParser(
        description="Classify a rabbit-managed issue per the seven-rule "
                    "triage decision table; emits JSON on stdout."
    )
    parser.add_argument("issue", type=int, help="GitHub issue number")
    args = parser.parse_args()

    repo_root = os.getcwd()

    try:
        result = classify(args.issue, repo_root)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or f"triage-issue: gh failed (exit {e.returncode})\n")
        sys.exit(e.returncode or 1)
    except Exception as e:
        # Per Inv 3 ambiguity default — but errors during the gh fetch
        # itself are caller-actionable, so we still exit non-zero on any
        # unexpected exception (not a classification ambiguity).
        sys.stderr.write(f"triage-issue: unexpected error: {e}\n")
        sys.exit(1)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
