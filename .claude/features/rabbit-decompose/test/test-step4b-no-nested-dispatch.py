#!/usr/bin/env python3
"""test-step4b-no-nested-dispatch.py — Step 4B direct-dispatch shape check.

End-to-end shape check of rabbit-decompose's spec-seeding hand-off step.

Since #922 the rabbit-spec-create skill WRAPPER is retired: the
rabbit-spec-creator SUBAGENT drafts AND writes its own docs/spec.md and is
dispatched DIRECTLY. rabbit-decompose Step 4-B is a main-session
orchestration, so it dispatches `rabbit-spec-creator` at LEVEL-1
(main session -> rabbit-spec-creator) via the input assembler
`scripts/dispatch-spec-creator.py`. There is no longer any intermediate
subagent-dispatching skill, so the old two-level-nesting workaround (which
forced the seeding calls to be sequential `Skill()` calls) no longer applies:
the N per-feature dispatches may now run in TRUE PARALLEL.

This test asserts, against BOTH the source SKILL.md and docs/spec.md:

  - Neither surface references the RETIRED `rabbit-spec-create` skill name,
    nor the OLD `dispatch-spec-create.py` script name.
  - Both surfaces name the NEW direct-dispatch path: the
    `dispatch-spec-creator.py` input assembler and a direct
    `rabbit-spec-creator` Agent dispatch.
  - The SKILL.md Step 4-B states the per-feature dispatches may run in
    parallel (the level-1 direct dispatch removed the sequential constraint).

Run non-interactively. Exits non-zero on failure.

Version: 0.2.0
Owner: rabbit-workflow team
Deprecation criterion: when the rabbit-spec-creator dispatch interface is
superseded by a native spec-lifecycle capability.
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

# 1. The retired skill name and the old script name must be GONE from both
#    surfaces. `rabbit-spec-create` is matched with a trailing boundary that
#    excludes `rabbit-spec-creator` (the subagent, which is the NEW target).
retired_patterns = [
    # the retired skill wrapper — but NOT rabbit-spec-creator (the subagent)
    (r"rabbit-spec-create(?!r)", "retired rabbit-spec-create skill"),
    # the old input-assembler script name (renamed to dispatch-spec-creator.py)
    (r"dispatch-spec-create\.py", "old dispatch-spec-create.py script name"),
]
for surface_name, text in (("SKILL.md", skill_text), ("docs/spec.md", spec_text)):
    for pat, label in retired_patterns:
        m = re.search(pat, text)
        if m:
            fail(
                f"{surface_name} still references {label}: "
                f"matched {pat!r} -> {m.group(0)!r}"
            )

# 2. Both surfaces must name the NEW direct-dispatch path: the input
#    assembler script and the rabbit-spec-creator subagent.
for surface_name, text in (("SKILL.md", skill_text), ("docs/spec.md", spec_text)):
    if "dispatch-spec-creator.py" not in text:
        fail(
            f"{surface_name} does not reference the dispatch-spec-creator.py "
            f"input assembler (the new direct-dispatch path)"
        )
    if "rabbit-spec-creator" not in text:
        fail(
            f"{surface_name} does not name the rabbit-spec-creator subagent "
            f"(the direct level-1 dispatch target)"
        )

# 3. The SKILL.md must dispatch the subagent DIRECTLY via the Agent tool
#    (level-1), not via a Skill() wrapper.
if not re.search(
    r"Agent\(\s*subagent_type\s*[:=]\s*[\"']rabbit-spec-creator", skill_text
):
    fail(
        "SKILL.md Step 4-B does not dispatch rabbit-spec-creator directly via "
        "Agent(subagent_type: \"rabbit-spec-creator\", ...) (level-1 dispatch)"
    )

# 4. The SKILL.md Step 4-B must state the per-feature dispatches may run in
#    PARALLEL — the level-1 direct dispatch removed the old sequential
#    two-level-nesting constraint.
if not re.search(r"parallel", skill_text, re.IGNORECASE):
    fail(
        "SKILL.md Step 4-B does not state the rabbit-spec-creator dispatches "
        "may run in parallel (the level-1 direct dispatch removed the "
        "sequential constraint)"
    )

print("All checks passed.")
