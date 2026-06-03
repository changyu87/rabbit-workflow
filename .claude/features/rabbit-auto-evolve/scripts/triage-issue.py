#!/usr/bin/env python3
"""triage-issue.py — classify a single rabbit-managed issue (Inv 3).

Per rabbit-auto-evolve spec.md Inv 3, emits a JSON object on stdout with
fields: issue, decision, reason_code, rationale, feature, features,
contract_touch, priority, blocked_by, planning_note. The `priority` field
(issue #484) echoes the issue's priority:<level> label value (None when
absent); plan-batch.py folds it into the loop's computed priority score as
ONE weighted input among several (Inv 46 / issue #441, refining the
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
    number,title,body,labels,state,stateReason,comments`. The full comment
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

Version: 1.7.0
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


# Match `blocked-by: #N` (case-insensitive). Captures the integer N.
_BLOCKED_BY_GOOD = re.compile(r"blocked-by:\s*#(\d+)", re.IGNORECASE)
# Match `blocked-by:` declared at all (used to detect malformed variants).
_BLOCKED_BY_ANY = re.compile(r"blocked-by:", re.IGNORECASE)


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
    issue = _gh_issue_view(
        issue_num, "number,title,body,labels,state,stateReason,comments"
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
    ctouch = _contract_touch(labels, body)
    # Canonical feature vocabulary (discovered from .claude/features/) — the
    # basis for Stage-2 bare-name cross-feature detection (issue #443).
    feature_names = _discover_feature_names(repo_root)

    base = {
        "issue": issue_num,
        "feature": feature_label,
        # `features` is the distinct set of feature dirs the item touches —
        # the union of (a) the feature label, (b) `.claude/features/<name>/`
        # body path references, and (c) bare feature names matched word-for-
        # word in the body/title (issue #443). The Stage-2 dispatch-shape
        # basis (Inv 26 / issue #435). Always present; for a malformed-labels
        # issue with no body paths and no bare-name mention it is [].
        "features": _feature_set(feature_label, body, title, feature_names),
        "contract_touch": ctouch,
        # `priority` (issue #484) echoes the issue's priority:<level> label
        # value (None when absent). plan-batch.py folds it into the loop's
        # computed priority score as ONE weighted input (Inv 46 / issue #441,
        # refining the priority-primary key of Inv 4 / issue #479); a None
        # filer label simply contributes nothing to the score.
        "priority": priority_label,
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
    if _BLOCKED_BY_ANY.search(body):
        matches = _BLOCKED_BY_GOOD.findall(body)
        if not matches:
            # Declared but malformed — ambiguity default.
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
