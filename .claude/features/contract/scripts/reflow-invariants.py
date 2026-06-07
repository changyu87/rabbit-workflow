#!/usr/bin/env python3
"""reflow-invariants.py — CLI shim around contract.lib.reflow.reflow_feature.

Renumbers a feature's invariants to contiguous 1..N (closing gaps left by
retired invariants) and atomically rewrites every live `Inv N` cross-reference
across that feature's own surfaces (spec.md, contract.md, skills/*/SKILL.md,
lib/*.py, scripts/**, test/*.py, templates/**). docs/CHANGELOG.md is never
touched — its tombstones are point-in-time history.

Usage:
  reflow-invariants.py <feature-dir> [--dry-run]

  --dry-run   print the renumber map and the files that WOULD change; write
              nothing.

Exit: 0 on success (incl. already-contiguous no-op); 1 on error (missing /
      unparsable spec); 2 on invocation error.

Per-feature only: each invocation reflows a single feature. Cross-feature
reference rewriting is intentionally NOT done — a feature owns its own
invariant numbering and references to OTHER features' invariants are addressed
by reflowing that other feature in its own scope.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when invariant numbering is folded into a structured,
schema-tracked log that renumbers via data rather than text.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
from lib.reflow import reflow_feature  # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    dry_run = False
    positional = []
    for a in args:
        if a == "--dry-run":
            dry_run = True
        elif a.startswith("-"):
            print(f"ERROR: unknown flag {a}", file=sys.stderr)
            return 2
        else:
            positional.append(a)

    if len(positional) != 1:
        print(
            "ERROR: usage: reflow-invariants.py <feature-dir> [--dry-run]",
            file=sys.stderr,
        )
        return 2

    feature_dir = positional[0]
    if not os.path.isdir(feature_dir):
        print(f"ERROR: not a directory: {feature_dir}", file=sys.stderr)
        return 2

    result = reflow_feature(feature_dir, dry_run=dry_run)
    for line in result.messages:
        print(line)
    if result.renumber_map:
        print("renumber map (old -> new):")
        for old in sorted(result.renumber_map):
            print(f"  {old} -> {result.renumber_map[old]}")
    for path in result.files_changed:
        print(f"  {'WOULD CHANGE' if dry_run else 'CHANGED'}: {path}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
