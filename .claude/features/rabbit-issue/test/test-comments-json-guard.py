"""Guard + e2e tests for reading issue comments via the JSON API (#522).

`gh issue view <N> --comments` triggers a deprecated Projects-classic
`projectCards` GraphQL field that FAILS and returns an EMPTY body on this
repo, so comments silently read as absent even when present — a
correctness trap, not a loud error. The sanctioned path is
`gh issue view <N> --json comments` (parse the JSON), which does not hit
the deprecated field.

Invariants enforced:

  1. No rabbit-issue runtime script (scripts/*.py) contains the literal
     `gh issue view … --comments` human-view flag for reading comments.
  2. The SKILL.md body MUST NOT direct comment reads through `--comments`,
     and MUST name the `--json comments` form.
  3. `_gh.py` exposes `gh_issue_comments(number)` and reads comments via
     `gh issue view <N> -R <slug> --json comments` (asserted against the
     gh shim call log), returning the parsed comment list (each item
     carrying a `body`).

(1) and (2) are static grep-style guards; (3) is an e2e test against the
PATH-resident gh shim.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = FEATURE_DIR / "scripts"
SKILL_MD = FEATURE_DIR / "skills" / "rabbit-issue" / "SKILL.md"

sys.path.insert(0, str(SCRIPTS_DIR))

# Matches `gh issue view <anything> --comments` — the deprecated human
# view. Tolerates intervening flags/args between `view` and `--comments`.
DEPRECATED_COMMENTS_RE = re.compile(r"issue\s+view\b[^\n]*?--comments\b")

# A `--comments` mention is tolerated only when the same source line
# negates it — i.e. a docstring/comment explaining the deprecated path,
# never a live invocation. Prescriptive (un-negated) usage is the bug.
_NEGATIONS = ("never", "not", "NOT", "deprecated")


def _negated(line: str) -> bool:
    return any(w in line for w in _NEGATIONS)


def _prescriptive_offenders(text: str) -> list:
    """Lines that match the deprecated form WITHOUT a negating word."""
    return [
        line.strip()
        for line in text.splitlines()
        if DEPRECATED_COMMENTS_RE.search(line) and not _negated(line)
    ]


def _scripts():
    return sorted(SCRIPTS_DIR.glob("*.py"))


def test_no_script_uses_deprecated_comments_flag():
    """Inv 1: no runtime script reads comments via `gh issue view --comments`.

    A `--comments` mention is allowed only in negated docstring/comment
    prose (e.g. "the `--comments` view is NOT used"); a live, prescriptive
    invocation is the regression this guards against (#522).
    """
    offenders = {}
    for script in _scripts():
        bad = _prescriptive_offenders(script.read_text())
        if bad:
            offenders[script.name] = bad
    assert not offenders, (
        "rabbit-issue scripts use the deprecated `gh issue view --comments` "
        "human view (hits projectCards GraphQL, returns empty — #522); use "
        "`--json comments` instead. Offenders: {}".format(offenders)
    )


def test_skill_does_not_direct_comments_flag():
    """Inv 2: SKILL.md must not PRESCRIBE comment reads via `--comments`.

    The SKILL legitimately *names* the deprecated `--comments` view inside
    its warning prose ("never the human view `gh issue view <N>
    --comments`"). What is forbidden is presenting it as the way to read
    comments. We allow a `--comments` mention only on a line that also
    negates it (`never`/`not`/`NOT`).
    """
    offenders = _prescriptive_offenders(SKILL_MD.read_text())
    assert not offenders, (
        "SKILL.md prescribes comment reads via deprecated "
        "`gh issue view --comments` without negation (#522); use "
        "`--json comments`. Offending lines: {}".format(offenders)
    )


def test_skill_names_json_comments_form():
    """Inv 2: SKILL.md must name the sanctioned `--json comments` path."""
    body = SKILL_MD.read_text()
    assert "--json comments" in body, (
        "SKILL.md must name `gh issue view <N> --json comments` as the "
        "sanctioned comment-read path (#522)."
    )


def test_gh_issue_comments_uses_json_api(gh_shim, fake_repo, monkeypatch):
    """Inv 3: gh_issue_comments calls `--json comments` and parses the JSON."""
    monkeypatch.setenv("RABBIT_ISSUE_REPO", "test/repo")
    sys.modules.pop("_gh", None)
    import _gh  # noqa: F401

    assert hasattr(_gh, "gh_issue_comments"), (
        "_gh.py must expose gh_issue_comments(number) (#522)"
    )

    comments = _gh.gh_issue_comments(42)

    # The shim returns a comments payload; the helper must parse it to the
    # list of comment objects (not the raw {"comments": [...]} envelope).
    assert isinstance(comments, list)
    assert any(c.get("body") for c in comments), (
        "gh_issue_comments must return parsed comment objects carrying bodies"
    )

    # And it MUST have gone through the JSON API, not the --comments view.
    log = gh_shim.read_text()
    assert "--json comments" in log, (
        "gh_issue_comments must read via `gh issue view --json comments`"
    )
    assert not DEPRECATED_COMMENTS_RE.search(log), (
        "gh_issue_comments must not use the deprecated `--comments` view"
    )
