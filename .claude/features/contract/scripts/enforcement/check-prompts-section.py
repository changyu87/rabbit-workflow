#!/usr/bin/env python3
"""check-prompts-section.py — thin CLI shim around
contract.lib.checks.check_prompts_section (spec Inv 51, 52, 53, 37).

Usage: check-prompts-section.py [<features-root>]
Exit:  0 no violations; 1 violations found; 2 invocation error.

<features-root> defaults to <git-rev-parse-show-toplevel>/.claude/features.

The check walks every feature.json under <features-root>, validates each
present prompts section against prompts.schema.json, asserts globally-unique
ids, asserts every inject path resolves on disk, asserts every entry's inject
list includes .claude/features/policy/philosophy.md, and asserts bidirectional
slot/placeholder correspondence against
.claude/features/contract/templates/prompts/<id>.txt.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when prompt-contract assembly becomes native to
Claude Code and the @-import / slot pipeline is no longer feature-owned.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_prompts_section  # noqa: E402


def main() -> int:
    if len(sys.argv) > 2:
        print(
            "ERROR: usage: check-prompts-section.py [<features-root>]",
            file=sys.stderr,
        )
        return 2
    if len(sys.argv) == 2:
        features_root = sys.argv[1]
    else:
        try:
            repo_root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"ERROR: cannot determine repo root: {e}", file=sys.stderr)
            return 2
        features_root = os.path.join(repo_root, ".claude", "features")
    if not os.path.isdir(features_root):
        print(f"ERROR: not a directory: {features_root}", file=sys.stderr)
        return 2
    result = check_prompts_section(features_root)
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
