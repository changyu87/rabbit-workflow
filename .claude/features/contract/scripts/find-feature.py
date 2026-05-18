#!/usr/bin/env python3
"""find-feature.py — distributed feature registry lookup.

Usage (invoked by find-feature.sh):
  python3 find-feature.py <repo-root> list
  python3 find-feature.py <repo-root> list-json
  python3 find-feature.py <repo-root> lookup <feature-name>

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when feature discovery is handled natively by the dispatch infrastructure.
"""

import json
import os
import sys
import glob


def iter_feature_jsons(repo):
    """Yield all feature.json paths: rabbit-level + project-level."""
    # Rabbit-level features
    for fj in sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json'))):
        yield fj
    # Project-level features
    try:
        entries = sorted(os.listdir(repo))
    except Exception:
        return
    for entry in entries:
        feat_base = os.path.join(repo, entry, 'features')
        if os.path.isdir(feat_base):
            for fname in sorted(os.listdir(feat_base)):
                fj = os.path.join(feat_base, fname, 'feature.json')
                if os.path.isfile(fj):
                    yield fj


def cmd_list(repo):
    for fj in iter_feature_jsons(repo):
        try:
            name = json.load(open(fj)).get('name', '')
            if name:
                print(name)
        except Exception:
            pass


def cmd_list_json(repo):
    results = []
    for fj in iter_feature_jsons(repo):
        try:
            f = json.load(open(fj))
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
            f = json.load(open(fj))
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
