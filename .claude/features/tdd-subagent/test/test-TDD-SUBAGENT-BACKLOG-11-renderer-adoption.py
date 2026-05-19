#!/usr/bin/env python3
"""test-TDD-SUBAGENT-BACKLOG-11-renderer-adoption.py

Spec Inv 5 (rewritten): tdd-step.py MUST NOT contain direct ANSI escape codes,
the literal `[rabbit]` brand string, the literal `[🐇 rabbit 🐇]` brand string,
or the bar character `━━━` in its source (outside of import statements and
comments). Instead it MUST import and use rabbit_print and rabbit_subline from
the centralized contract renderer.

This test greps the tdd-step.py source for those forbidden literals and asserts
the required import is present.
"""
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def _strip_comments(lines):
    """Return list of (lineno, content) for non-comment, non-blank lines.

    A line is considered a comment if its first non-whitespace character is '#'.
    Trailing inline comments are stripped (best-effort, ignoring '#' inside
    string literals is not necessary because we only assert ABSENCE of certain
    tokens; any false positive inside a string would still be a real source
    occurrence that must not exist).
    """
    out = []
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            continue
        out.append((i, line))
    return out


def _is_import_line(line):
    s = line.lstrip()
    return s.startswith('import ') or s.startswith('from ')


with open(TDD_STEP) as f:
    src = f.read()
lines = src.splitlines()
code_lines = _strip_comments(lines)

# (a) No raw ANSI escape sequences.
ansi_hits = []
for ln, content in code_lines:
    if _is_import_line(content):
        continue
    if '\\x1b' in content or '\\033' in content:
        ansi_hits.append((ln, content.rstrip()))
if not ansi_hits:
    ok('no raw ANSI escape sequences (\\x1b / \\033) in tdd-step.py body')
else:
    ko(f'found ANSI escape literals at: {ansi_hits}')

# (b) No literal "[rabbit]" string.
brand_hits = []
for ln, content in code_lines:
    if _is_import_line(content):
        continue
    if '[rabbit]' in content:
        brand_hits.append((ln, content.rstrip()))
if not brand_hits:
    ok('no literal "[rabbit]" brand string in tdd-step.py body')
else:
    ko(f'found "[rabbit]" literal at: {brand_hits}')

# (b2) No literal "[🐇 rabbit 🐇]" string either.
brand2_hits = []
for ln, content in code_lines:
    if _is_import_line(content):
        continue
    if '[\U0001f407 rabbit \U0001f407]' in content:
        brand2_hits.append((ln, content.rstrip()))
if not brand2_hits:
    ok('no literal "[🐇 rabbit 🐇]" brand string in tdd-step.py body')
else:
    ko(f'found rabbit-emoji brand literal at: {brand2_hits}')

# (c) No literal "━━━" bar string.
bar_hits = []
for ln, content in code_lines:
    if _is_import_line(content):
        continue
    if '━━━' in content:
        bar_hits.append((ln, content.rstrip()))
if not bar_hits:
    ok('no literal "━━━" bar string in tdd-step.py body')
else:
    ko(f'found bar literal at: {bar_hits}')

# (d) Required import present. The line may carry a trailing comment such as
# `# noqa: E402` so we match the import prefix, not the whole line.
if re.search(r'^\s*from\s+rabbit_print\s+import\s+rabbit_print\s*,\s*rabbit_subline\b',
             src, re.MULTILINE):
    ok('imports "from rabbit_print import rabbit_print, rabbit_subline"')
else:
    ko('required import "from rabbit_print import rabbit_print, rabbit_subline" not found')

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
