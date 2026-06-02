#!/usr/bin/env python3
"""find-feature.py — distributed feature registry lookup.

Usage:
  python3 find-feature.py <repo-root> list
  python3 find-feature.py <repo-root> list-json
  python3 find-feature.py <repo-root> lookup <feature-name>

Scope: scans TWO canonical feature-root locations per Inv 23:
  (a) `<repo>/.claude/features/<name>/feature.json` — always.
  (b) `<repo>/.rabbit/rabbit-project/features/<name>/feature.json` — ONLY
      when `<repo>/.rabbit/.runtime/mode` exists and its content equals
      `"plugin"`. This surfaces user-project features in plugin installs.
Directories elsewhere in the repo whose basename happens to be `features`
(project-side, vendor dirs, etc.) are NOT scanned — the no-masquerading
guarantee is preserved by enumerating only the two canonical paths above.

Version: 1.2.0
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


def _is_plugin_mode(repo):
    """Detect plugin mode via the standard `.rabbit/.runtime/mode` marker."""
    mode_file = os.path.join(repo, '.rabbit', '.runtime', 'mode')
    try:
        with open(mode_file) as f:
            return f.read().strip() == 'plugin'
    except (OSError, IOError):
        return False


def iter_feature_jsons(repo):
    """Yield feature.json paths from the two canonical scan locations (Inv 23).

    Always yields `.claude/features/<name>/feature.json` first (alphabetical).
    In plugin mode (per `.rabbit/.runtime/mode == "plugin"`), additionally
    yields `.rabbit/rabbit-project/features/<name>/feature.json` next
    (alphabetical). No deduplication — callers needing uniqueness enforce
    it themselves.
    """
    for fj in sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json'))):
        yield fj
    if _is_plugin_mode(repo):
        for fj in sorted(glob.glob(os.path.join(repo, '.rabbit', 'rabbit-project', 'features', '*', 'feature.json'))):
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
