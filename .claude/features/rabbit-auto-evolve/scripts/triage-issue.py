#!/usr/bin/env python3
"""triage-issue.py — classify a single rabbit-managed issue (Inv 3).

Per rabbit-auto-evolve spec.md Inv 3, emits a JSON object on stdout with
fields: issue, decision, reason_code, rationale, feature, contract_touch,
blocked_by. Implements the seven-rule decision table (top-down, first
match wins); any ambiguity defaults to decision=defer, reason_code=
needs-judgment (never silently to work).

Read surface (strictly bounded):
  - Issue metadata via `gh issue view <N> --json
    number,title,body,labels,state,comments`.
  - The named feature's docs/spec/spec.md head matter (frontmatter +
    first section) — for rule 6 only.
  - The named feature's feature.json — for rule 4 (status field).
  - The last-30-days closed-issue list via `gh issue list --state closed
    --search "closed:>=<iso-date>"` — for rule 3.

No filesystem mutations. No reads outside the above surface.

Repo discovery uses rabbit-issue/_gh.repo_slug (sys.path bridge, same
pattern as fetch-queue.py).

Exit code: 0 on successful classification (any decision); non-zero on gh
failure or other unexpected error (stderr passthrough).

Version: 1.0.0
Owner: cyxu
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


def _read_spec_head_matter(feature_dir):
    """Read the first ~4KB of feature_dir/docs/spec/spec.md (frontmatter +
    first section) for rule-6 matching. Returns "" if absent."""
    spec_path = feature_dir / "docs" / "spec" / "spec.md"
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


# Match `blocked-by: #N` (case-insensitive). Captures the integer N.
_BLOCKED_BY_GOOD = re.compile(r"blocked-by:\s*#(\d+)", re.IGNORECASE)
# Match `blocked-by:` declared at all (used to detect malformed variants).
_BLOCKED_BY_ANY = re.compile(r"blocked-by:", re.IGNORECASE)


def classify(issue_num, repo_root):
    """Run the seven-rule decision table. Returns a dict ready for json.dump."""
    # ---- Fetch issue metadata ----
    issue = _gh_issue_view(
        issue_num, "number,title,body,labels,state,comments"
    )

    title = issue.get("title", "") or ""
    body = issue.get("body", "") or ""
    labels = issue.get("labels", []) or []

    feature_label = _label_value(labels, "feature")
    priority_label = _label_value(labels, "priority")
    ctouch = _contract_touch(labels, body)

    base = {
        "issue": issue_num,
        "feature": feature_label,
        "contract_touch": ctouch,
        "blocked_by": [],
    }

    # ---- Rule 1: malformed-labels ----
    if not feature_label or not priority_label:
        return dict(base,
                    decision="defer",
                    reason_code="malformed-labels",
                    rationale="Issue is missing required feature: or priority: label.")

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
                    rationale="Could not query closed-issue list for duplicate check.")

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
                        rationale="Body declares 'blocked-by:' but no integer issue reference found.")
        blocked_open = []
        for n in matches:
            n_int = int(n)
            try:
                dep = _gh_issue_view(n_int, "number,state")
            except subprocess.CalledProcessError:
                return dict(base,
                            decision="defer",
                            reason_code="needs-judgment",
                            rationale=f"Could not query state of cited dependency #{n_int}.")
            dep_state = (dep.get("state") or "").upper()
            if dep_state == "OPEN":
                blocked_open.append(n_int)
        if blocked_open:
            return dict(base,
                        decision="defer",
                        reason_code="blocked",
                        rationale=f"Blocked by still-open issue(s): {blocked_open}.",
                        blocked_by=blocked_open)

    # ---- Rule 6: already-spec'd ----
    head_matter = _read_spec_head_matter(feature_dir).casefold()
    tail = _title_tail(title)
    if tail and len(tail) >= 3 and tail in head_matter:
        return dict(base,
                    decision="close-not-planned",
                    reason_code="already-spec'd",
                    rationale="Spec head matter already documents this behavior (title-tail substring match).")

    # ---- Rule 7: actionable / work ----
    return dict(base,
                decision="work",
                reason_code="actionable",
                rationale="No earlier rule matched; issue is actionable.")


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
