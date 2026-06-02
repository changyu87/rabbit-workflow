#!/usr/bin/env python3
"""find-feature.py — distributed feature registry lookup.

Usage:
  python3 find-feature.py <repo-root> list
  python3 find-feature.py <repo-root> list-json
  python3 find-feature.py <repo-root> lookup <feature-name>

Scope: dual-detects plugin mode per Inv 23 (amended). The `<repo>`
argument MAY be EITHER the host-project root OR the rabbit install root
(`RABBIT_ROOT` — the `.rabbit/` install dir); the script resolves the
canonical `rabbit_root` from whichever was supplied.

  Plugin mode detection (either path):
    (i)  <repo>/.rabbit/.runtime/mode == "plugin"  → rabbit_root=<repo>/.rabbit
    (ii) <repo>/.runtime/mode == "plugin"          → rabbit_root=<repo>

  Standalone scan (no marker matched):
    - <repo>/.claude/features/<name>/feature.json (alphabetical)

  Plugin scan (either detection path matched):
    - <rabbit_root>/.claude/features/<name>/feature.json   (alphabetical)
    - <rabbit_root>/rabbit-project/features/<name>/feature.json (alphabetical)

Directories elsewhere in the repo whose basename happens to be `features`
(project-side, vendor dirs, etc.) are NOT scanned — the no-masquerading
guarantee is preserved by enumerating only the canonical paths above.

Version: 1.3.0
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


def _detect_plugin_rabbit_root(repo):
    """Return rabbit_root (absolute path) if plugin mode is detected, else None.

    Plugin mode is detected via EITHER:
      - <repo>/.rabbit/.runtime/mode == 'plugin'  (repo is the host root)
          → rabbit_root = <repo>/.rabbit
      - <repo>/.runtime/mode == 'plugin'  (repo IS the rabbit_root)
          → rabbit_root = <repo>
    """
    for candidate, rabbit_root in (
        (os.path.join(repo, '.rabbit', '.runtime', 'mode'), os.path.join(repo, '.rabbit')),
        (os.path.join(repo, '.runtime', 'mode'), repo),
    ):
        try:
            with open(candidate) as f:
                if f.read().strip() == 'plugin':
                    return rabbit_root
        except (OSError, IOError):
            continue
    return None


def iter_feature_jsons(repo):
    """Yield feature.json paths from the canonical scan locations (Inv 23 amended).

    Standalone (no plugin marker): yields only
    `<repo>/.claude/features/<name>/feature.json` (alphabetical).

    Plugin (marker matched via either detection path): yields
    `<rabbit_root>/.claude/features/<name>/feature.json` first then
    `<rabbit_root>/rabbit-project/features/<name>/feature.json`,
    alphabetical within each. No deduplication — callers needing
    uniqueness enforce it themselves.
    """
    rabbit_root = _detect_plugin_rabbit_root(repo)
    if rabbit_root is None:
        for fj in sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json'))):
            yield fj
    else:
        for fj in sorted(glob.glob(os.path.join(rabbit_root, '.claude', 'features', '*', 'feature.json'))):
            yield fj
        for fj in sorted(glob.glob(os.path.join(rabbit_root, 'rabbit-project', 'features', '*', 'feature.json'))):
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
