#!/usr/bin/env python3
"""find-feature.py — distributed feature registry lookup.

Usage:
  python3 find-feature.py <repo-root> list
  python3 find-feature.py <repo-root> list-json
  python3 find-feature.py <repo-root> lookup <feature-name>

Scope: scans ONLY `.claude/features/` for feature directories. Directories
elsewhere in the repo whose basename happens to be `features` (project-side,
vendor dirs, etc.) are NOT scanned per Inv 28.

Version: 1.1.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when feature discovery is handled natively by the dispatch infrastructure.
"""

import json
import os
import sys
import glob


def _load_json(path):
    """Open with context manager to ensure handle is closed."""
    with open(path) as f:
        return json.load(f)


def iter_feature_jsons(repo):
    """Yield all feature.json paths under `.claude/features/` only.

    Project-side `<root>/features/` trees are explicitly out of scope per
    Inv 28 — scanning them would let any directory named `features`
    masquerade as a feature root.
    """
    for fj in sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json'))):
        yield fj


def cmd_list(repo):
    for fj in iter_feature_jsons(repo):
        try:
            data = _load_json(fj)
            name = data.get('name', '')
            if name:
                print(name)
        except Exception:
            pass


def cmd_list_json(repo):
    results = []
    for fj in iter_feature_jsons(repo):
        try:
            f = _load_json(fj)
            results.append({
                'name': f.get('name', ''),
                'path': os.path.relpath(os.path.dirname(fj), repo),
                'summary': f.get('summary', ''),
                'tdd_state': f.get('tdd_state', ''),
            })
        except Exception:
            pass
    print(json.dumps(results))


def cmd_lookup(repo, target):
    for fj in iter_feature_jsons(repo):
        try:
            f = _load_json(fj)
            if f.get('name', '') == target:
                print(os.path.relpath(os.path.dirname(fj), repo))
                sys.exit(0)
        except Exception:
            pass
    # Not found — exit 1 (caller checks)
    sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"usage: {sys.argv[0]} <repo-root> list|list-json|lookup [feature-name]", file=sys.stderr)
        sys.exit(2)

    repo = sys.argv[1]
    subcmd = sys.argv[2]

    if subcmd == 'list':
        cmd_list(repo)
    elif subcmd == 'list-json':
        cmd_list_json(repo)
    elif subcmd == 'lookup':
        if len(sys.argv) < 4:
            print("ERROR: lookup requires <feature-name>", file=sys.stderr)
            sys.exit(2)
        cmd_lookup(repo, sys.argv[3])
    else:
        print(f"ERROR: unknown subcommand '{subcmd}'", file=sys.stderr)
        sys.exit(2)
