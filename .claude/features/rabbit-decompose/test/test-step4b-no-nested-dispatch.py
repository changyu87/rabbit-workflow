#!/usr/bin/env python3
"""test-step4b-no-nested-dispatch.py — Step 4B nesting-safety guard.

End-to-end shape check of rabbit-decompose's spec-create hand-off step.

rabbit-spec-create is a skill that INTERNALLY dispatches the
rabbit-spec-creator subagent via the Agent tool. Wrapping such a
subagent-dispatching skill inside another Agent() call from rabbit-decompose
would create a two-level subagent nesting chain
(decompose -> Agent level-1 -> rabbit-spec-creator level-2), which Claude
Code does not support: the level-2 dispatch is blocked / silently dropped.

The correct, unblocked hand-off therefore invokes rabbit-spec-create as
SEQUENTIAL Skill() calls from the main session context, where
rabbit-spec-creator is always a level-1 subagent (main session ->
rabbit-spec-creator).

This test asserts, against BOTH the source SKILL.md and docs/spec.md:

  - Neither surface tells the reader to run / parallelize rabbit-spec-create
    via the Agent tool (the illegal two-level-nesting claim is absent).
  - The SKILL.md hand-off step states the spec-create calls run
    sequentially.
  - At least one surface names the two-level-nesting constraint (a
    subagent-dispatching skill must not be wrapped in Agent()).

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code supports nested subagent dispatch,
making the sequential level-1 hand-off constraint obsolete.
"""
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL_MD = os.path.join(
    FEATURE_DIR, "skills", "rabbit-decompose", "SKILL.md"
)
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec.md")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def read_text(path, label):
    if not os.path.isfile(path):
        fail(f"{label}: missing file: {path}")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        fail(f"{label}: empty file: {path}")
    return text


skill_text = read_text(SKILL_MD, "SKILL.md")
spec_text = read_text(SPEC_MD, "docs/spec.md")

# 1. No surface may make the POSITIVE claim that rabbit-spec-create can be
#    run / parallelized via the Agent tool — that is the illegal
#    two-level-nesting claim the fix removes.
#
#    Note: a correct surface still *mentions* the Agent tool — to explain that
#    rabbit-spec-create internally dispatches its subagent via Agent, and to
#    forbid wrapping it (e.g. "may NOT be parallelized via the Agent tool").
#    So we must match the asserting/permitting form, not every Agent mention.
#    Each pattern below requires an enabling verb (can/may/run/parallelize)
#    bound to spec-create + Agent, and must NOT be immediately negated.
illegal_patterns = [
    # "... rabbit-spec-create ... can be run in parallel via the Agent tool ..."
    r"(?:can|may)\s+be\s+run\s+in\s+parallel\s+via\s+(?:the\s+)?Agent",
    # "... MAY run in parallel via independent Agent dispatches ..."
    r"(?:can|may)\s+run\s+in\s+parallel\s+via\s+(?:\w+\s+){0,3}Agent",
    # "... run in parallel via the Agent tool for batch parallelism ..."
    r"in\s+parallel\s+via\s+(?:the\s+)?Agent\s+tool\s+for\s+batch",
    # "... parallel via independent Agent dispatches ..."
    r"parallel\s+via\s+independent\s+Agent\s+dispatch",
]

NEGATION = re.compile(
    r"\b(?:not|never|MUST\s+NOT|MUST\s+NEVER|no\b|cannot|can't|may\s+not)\b",
    re.IGNORECASE,
)


def _negated_window(text, start):
    # Look back up to 60 chars from the match start for an explicit negation,
    # so a prohibition ("may NOT ... parallel via Agent") is not flagged.
    window = text[max(0, start - 60):start]
    return bool(NEGATION.search(window))


for surface_name, text in (("SKILL.md", skill_text), ("docs/spec.md", spec_text)):
    for pat in illegal_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            if _negated_window(text, m.start()):
                continue
            fail(
                f"{surface_name} still claims rabbit-spec-create can be "
                f"Agent-parallelized (illegal 2-level nesting): "
                f"matched {pat!r} -> {m.group(0)!r}"
            )

# 2. The SKILL.md spec-create hand-off must state the calls run sequentially.
if not re.search(r"sequential", skill_text, re.IGNORECASE):
    fail(
        "SKILL.md does not state the rabbit-spec-create calls run "
        "sequentially (level-1 hand-off)"
    )

# 3. At least one surface must name the two-level-nesting constraint: a
#    subagent-dispatching skill must not be wrapped in an Agent() call.
combined = skill_text + "\n" + spec_text
nesting_constraint = re.search(
    r"(two-level|2-level)\s+nesting", combined, re.IGNORECASE
) or re.search(
    r"nest(?:ed|ing).*(?:subagent|Agent)", combined, re.IGNORECASE
)
if not nesting_constraint:
    fail(
        "no surface names the two-level subagent-nesting constraint that "
        "justifies the sequential level-1 hand-off"
    )

print("All checks passed.")
