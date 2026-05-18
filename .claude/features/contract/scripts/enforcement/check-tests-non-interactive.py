#!/usr/bin/env python3
# check-tests-non-interactive.py — fail if any Python test file under
# <feature-dir>/test/ uses interactive constructs that would block an
# end-to-end run.
#
# Per the rabbit workflow rule: "for TDD steps, when you do test, it must be a
# hard end-to-end test with no human intervention."
#
# Scans .py files only — the repo is Python-only (rabbit-cage Inv 39,
# rabbit-file Tech Stack). Detects bare input(), getpass.getpass(),
# click.prompt(), click.confirm().
#
# Usage: check-tests-non-interactive.py <feature-dir>
# Exit:  0 ok (no test/ dir, or test/ clean); 1 violations found.
#
# Version: 2.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when non-interactive enforcement is provided by a native linter.

import os
import re
import sys


# Patterns that indicate interactive input in Python source (after stripping
# comments). The lookbehind on input() rejects identifier-shadowed callers
# like my_input() or self.input() while still catching the bare builtin.
INTERACTIVE_PATTERNS = [
    (re.compile(r'(?<![A-Za-z0-9_.])input\s*\('), "bare input() call"),
    (re.compile(r'getpass\s*\.\s*getpass\s*\('), "getpass.getpass()"),
    (re.compile(r'click\s*\.\s*prompt\s*\('), "click.prompt()"),
    (re.compile(r'click\s*\.\s*confirm\s*\('), "click.confirm()"),
]


def strip_comments(code):
    """Remove lines that are pure Python comments."""
    lines = code.splitlines()
    filtered = [line for line in lines if not re.match(r'^\s*#', line)]
    return "\n".join(filtered)


def main():
    if len(sys.argv) < 2:
        print("usage: check-tests-non-interactive.py <feature-dir>", file=sys.stderr)
        sys.exit(2)

    feature_dir = sys.argv[1]
    test_dir = os.path.join(feature_dir, "test")

    if not os.path.isdir(test_dir):
        print(f"OK: no test/ in {feature_dir} (vacuous)")
        sys.exit(0)

    violations = 0

    for dirpath, _, filenames in os.walk(test_dir):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath) as f:
                raw = f.read()
            code = strip_comments(raw)

            for pattern, desc in INTERACTIVE_PATTERNS:
                if pattern.search(code):
                    print(f"VIOLATION: {fpath} uses {desc}.", file=sys.stderr)
                    violations += 1
                    break  # one violation per file is enough

    if violations > 0:
        print(f"FAIL: {violations} interactive construct(s) found in {test_dir}.", file=sys.stderr)
        sys.exit(1)

    print(f"OK: no interactive constructs in {test_dir}")
    sys.exit(0)


if __name__ == "__main__":
    main()
