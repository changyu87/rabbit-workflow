#!/usr/bin/env python3
# format-feature-context.py — read find-feature.py list-json output from stdin,
# emit a human-readable feature context block to stdout.
#
# Usage:
#   python3 find-feature.py <repo-root> list-json | python3 format-feature-context.py
#
# Input:  JSON array of {name, path, summary, tdd_state} objects on stdin.
# Output: formatted text block, one feature per entry, to stdout.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-feature-scope)
# Deprecation criterion: when feature-scope resolution is automated by the dispatch infrastructure.

import json
import sys

features = json.load(sys.stdin)
lines = []
for f in features:
    lines.append(f'Feature: {f["name"]}')
    lines.append(f'  Path: {f["path"]}')
    lines.append(f'  Summary: {f["summary"]}')
    lines.append('')
print('\n'.join(lines))
