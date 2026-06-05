#!/usr/bin/env python3
"""test-script-docstrings-no-historical-tags.py — Inv 13 doc-surface hygiene

End-to-end guard that contract's own script and lib MODULE DOCSTRINGS carry
no historical-burden issue/PR tags. The cross-feature gate
test-spec-bodies-no-historical-tags.py scans spec.md / contract.md /
SKILL.md only; module docstrings are the third doc surface this feature
ships, and they must describe the current design only. Historical issue and
PR references (`#NNN`, `issue #NNN`, `PR #NNN`) belong in CHANGELOG.md and
commit messages, never in a docstring describing live behavior.

t1: every module docstring under scripts/ and lib/ is free of the
    historical-tag patterns.
"""

import ast
import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Matches bare issue/PR references: `#499`, `issue #468`, `PR #162`, `(#793)`.
# A 2+-digit run after `#` is the historical-tag shape; semver and version
# strings never carry a leading `#`, so this does not collide with `1.2.0`.
TAG_RE = re.compile(r"#\d{2,}")

PASS = 0
FAIL = 0


def module_docstring(path):
    with open(path) as f:
        try:
            return ast.get_docstring(ast.parse(f.read()))
        except SyntaxError:
            return None


violations = []
for sub in ("scripts", "lib"):
    base = os.path.join(FEATURE_DIR, sub)
    for dirpath, _, filenames in os.walk(base):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            ds = module_docstring(fpath)
            if not ds:
                continue
            for i, line in enumerate(ds.splitlines(), 1):
                if TAG_RE.search(line):
                    rel = os.path.relpath(fpath, FEATURE_DIR)
                    violations.append(f"{rel} docstring line {i}: {line.strip()}")

if not violations:
    print("  PASS t1: no historical-burden tags in script/lib module docstrings")
    PASS += 1
else:
    print("  FAIL t1: historical tags found in module docstrings:", file=sys.stderr)
    for v in violations:
        print(f"    {v}", file=sys.stderr)
    FAIL += 1

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
