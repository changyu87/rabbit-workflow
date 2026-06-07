#!/usr/bin/env python3
"""test-skill-description-triggers.py — SKILL.md `description:` frontmatter
enumerates the broadened natural-language trigger phrasings (spec Inv 43,
issue #415).

The `description:` line is the sole signal a fresh session uses to decide
whether to invoke the skill directly versus doing the "let me look around"
dance. It MUST recognize common natural phrasings — notably the unhyphenated
"auto evolve" and the "enter … mode" framing — in addition to the canonical
hyphenated commands.

This is an end-to-end assertion against the SOURCE SKILL.md (the artifact the
dispatcher publishes), reading the `description:` value out of the YAML
frontmatter exactly as the loader would.
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
SKILL_PATH = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-auto-evolve/skills/rabbit-auto-evolve/SKILL.md",
)


def _read_description(text):
    """Extract the `description:` value from the YAML frontmatter.

    The frontmatter is the block between the first two `---` fences. The
    description is a single-line scalar (may be long); YAML folds trailing
    indented continuation lines, but this SKILL.md keeps it on one logical
    line, so we read from `description:` to the next top-level key.
    """
    fm_m = re.search(r"(?s)\A---\n(.*?)\n---\n", text)
    if not fm_m:
        return None
    fm = fm_m.group(1)
    desc_m = re.search(
        r"(?ms)^description:\s*(.*?)(?=^\w[\w-]*:\s|\Z)", fm)
    if not desc_m:
        return None
    return " ".join(desc_m.group(1).split())


def main():
    if not os.path.isfile(SKILL_PATH):
        print(f"FAIL: SKILL.md does not exist at {SKILL_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(SKILL_PATH) as f:
        text = f.read()

    description = _read_description(text)
    if not description:
        print("FAIL: SKILL.md frontmatter has no `description:` value",
              file=sys.stderr)
        sys.exit(1)

    desc_lower = description.lower()

    # 1. Pre-existing canonical triggers MUST be retained (no regression).
    canonical = [
        "start auto-evolve",
        "stop the loop",
        "auto-evolve status",
        "let rabbit run",
        "begin autonomous evolve",
        "/rabbit-auto-evolve",
    ]
    for token in canonical:
        if token.lower() not in desc_lower:
            print(
                f"FAIL: Inv 43: SKILL.md description dropped the canonical "
                f"trigger phrasing: {token!r}",
                file=sys.stderr,
            )
            sys.exit(1)

    # 2. Broadened phrasings (issue #415) MUST be present.
    #    Each entry: (test-label, predicate-over-desc_lower).
    broadened = [
        ("enter auto* mode framing",
         "enter auto" in desc_lower),
        ("unhyphenated 'auto evolve'",
         "auto evolve" in desc_lower),
        ("the word 'mode' (enter … mode framing)",
         "mode" in desc_lower),
        ("enable/turn-on autonomous phrasing",
         ("turn on autonomous evolve" in desc_lower
          or "enable autonomous evolve" in desc_lower)),
        ("resume phrasing",
         "resume the loop" in desc_lower),
    ]
    for label, ok in broadened:
        if not ok:
            print(
                f"FAIL: Inv 43: SKILL.md description missing broadened "
                f"trigger phrasing: {label}",
                file=sys.stderr,
            )
            sys.exit(1)

    # 3. The description must stay a single coherent paragraph (SKILL.md
    #    authoring standard) — not split into a markdown list.
    if re.search(r"(?m)^\s*[-*]\s", description):
        print(
            "FAIL: Inv 43: SKILL.md description must remain a single coherent "
            "sentence/paragraph, not a bulleted list",
            file=sys.stderr,
        )
        sys.exit(1)

    print("PASS: test-skill-description-triggers.py")


if __name__ == "__main__":
    main()
