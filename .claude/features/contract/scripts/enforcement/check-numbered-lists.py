#!/usr/bin/env python3
"""check-numbered-lists.py — reject decimal/letter-suffix numbering in Markdown.

Scans `.md` files and rejects ordered-list items or headings that use:
  - decimal sub-numbers: `1.1`, `1.2.3`, `## 2.6 Foo`
  - letter-suffix numbering: `1a`, `3a)`, `## 3a Foo`

Plain `1.` / `2.` / `3.` ordered-list markers and plain integer headings
(`## 2 Foo`) are allowed.

Usage: check-numbered-lists.py <path> [<path> ...]
  Each <path> may be a `.md` file or a directory. Directories are walked
  recursively for `*.md` files.

Out-of-scope subtrees are skipped during directory walks:
  - any path containing `/archive/`
  - any path containing `/docs/superpowers/`

Exits 0 on no violations; exits 1 on any violation, with each violation
printed to stderr as `<path>:<line>: <pattern> <line-content>`.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when superseded by a generalized Markdown style linter.
"""

import os
import re
import sys

# Patterns to flag at line start (after optional leading whitespace, optional
# heading-hash run, optional list-bullet). Captured groups are not used; the
# match itself is the violation signal.
PATTERNS = [
    # `## 2.6 Foo` — heading with decimal sub-number.
    (re.compile(r"^\s*#{1,6}\s+\d+\.\d+(?:\.\d+)*\b"), "heading-decimal"),
    # `## 3a Foo` — heading with letter suffix.
    (re.compile(r"^\s*#{1,6}\s+\d+[a-z]\b"), "heading-letter"),
    # `1.2. item` or `- 1.2. item` — list item with decimal numbering.
    (re.compile(r"^\s*[-*+]?\s*\d+\.\d+(?:\.\d+)*\.\s"), "list-decimal"),
    # `3a) item` / `3a. item` / `3a: item` — list item with letter suffix.
    (re.compile(r"^\s*[-*+]?\s*\d+[a-z][.):]\s"), "list-letter"),
]

SKIP_SUBSTRINGS = ("/archive/", "/docs/superpowers/")


def is_skipped(path):
    norm = path.replace(os.sep, "/")
    return any(s in norm for s in SKIP_SUBSTRINGS)


def check_file(path):
    """Return list of (line_no, pattern_name, line_content) violations."""
    violations = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as e:
        print(f"ERROR: could not read {path}: {e}", file=sys.stderr)
        return [(0, "read-error", str(e))]
    in_fence = False
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        # Toggle fenced-code-block state on ``` or ~~~ at line start
        # (after optional whitespace).
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for rx, name in PATTERNS:
            if rx.match(line):
                violations.append((i, name, line.rstrip("\n")))
                break
    return violations


def collect_md_files(target):
    if os.path.isfile(target):
        if target.endswith(".md") and not is_skipped(target):
            yield target
        return
    for dirpath, dirnames, filenames in os.walk(target):
        # Prune skipped subtrees in-place for efficiency.
        if is_skipped(dirpath + os.sep):
            dirnames[:] = []
            continue
        for fname in filenames:
            if fname.endswith(".md"):
                p = os.path.join(dirpath, fname)
                if not is_skipped(p):
                    yield p


def main():
    if len(sys.argv) < 2:
        print(
            "ERROR: usage: check-numbered-lists.py <path> [<path> ...]",
            file=sys.stderr,
        )
        sys.exit(2)

    targets = sys.argv[1:]
    failed = 0
    for target in targets:
        if not os.path.exists(target):
            print(f"ERROR: not a file or directory: {target}", file=sys.stderr)
            failed = 1
            continue
        for md in collect_md_files(target):
            for line_no, name, content in check_file(md):
                print(f"{md}:{line_no}: {name} {content}", file=sys.stderr)
                failed = 1

    sys.exit(failed)


if __name__ == "__main__":
    main()
