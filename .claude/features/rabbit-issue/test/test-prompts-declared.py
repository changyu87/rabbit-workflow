#!/usr/bin/env python3
"""feature.json prompts contract for rabbit-issue.

`rabbit-issue.feature.json` MUST declare a `prompts` array with at least
one entry for the rabbit-issue skill prompt assembly:

  {"id": "rabbit-issue",
   "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["args"]}

The skill operates against GitHub Issues — code-authoring side-effects
through `gh` — so it inherits philosophy + coding-rules (not spec-rules;
rabbit-issue does not author specs).

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when prompt-contract assembly is native to Claude Code.
"""
import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"

EXPECTED_INJECT = [
    ".claude/features/policy/philosophy.md",
    ".claude/features/policy/coding-rules.md",
]


def main() -> int:
    data = json.loads(FEATURE_JSON.read_text())
    if "prompts" not in data:
        print("FAIL: feature.json missing top-level 'prompts'", file=sys.stderr)
        return 1
    prompts = data["prompts"]
    if not isinstance(prompts, list):
        print(f"FAIL: prompts must be list, got {type(prompts).__name__}",
              file=sys.stderr)
        return 1
    match = next(
        (p for p in prompts
         if isinstance(p, dict)
         and p.get("id") == "rabbit-issue"
         and p.get("kind") == "skill"),
        None,
    )
    if match is None:
        print("FAIL: feature.json prompts must declare a 'rabbit-issue' skill entry",
              file=sys.stderr)
        return 1
    inject = match.get("inject", [])
    missing = [p for p in EXPECTED_INJECT if p not in inject]
    if missing:
        print(f"FAIL: prompts[rabbit-issue].inject missing {missing}",
              file=sys.stderr)
        return 1
    slots = match.get("slots", [])
    if slots != ["args"]:
        print(f"FAIL: prompts[rabbit-issue].slots expected ['args'], got {slots!r}",
              file=sys.stderr)
        return 1
    print("PASS test-prompts-declared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
