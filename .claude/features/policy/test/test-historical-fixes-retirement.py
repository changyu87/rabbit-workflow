#!/usr/bin/env python3
"""test-historical-fixes-retirement.py — retirement watch for the historical
fixes kitchen-sink suite.

Reads `TICKETS_COVERED` from test-policy-bug-fixes.py (by text parsing — the
dashed-name file is not importable as a Python module), then scans
test-policy-invariants.py for `# Subsumes: <ticket-id>` marker comments.

Behavior:
- PASS while at least one ticket in TICKETS_COVERED is NOT yet subsumed.
  Prints the unsubsumed-count so progress is visible.
- FAIL once every ticket is subsumed — that failure is the explicit signal
  that test-policy-bug-fixes.py and this watch test MUST be deleted together
  (Inv 8, BACKLOG-14).

Traces: POLICY-BACKLOG-14 (created this watch test).

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: delete this file together with test-policy-bug-fixes.py
once every TICKETS_COVERED ticket is subsumed by test-policy-invariants.py.
"""
import ast
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUG_FIXES = os.path.join(FEATURE_DIR, "test", "test-policy-bug-fixes.py")
INVARIANTS = os.path.join(FEATURE_DIR, "test", "test-policy-invariants.py")


def parse_tickets_covered(path):
    """Extract the TICKETS_COVERED list literal via AST (no import)."""
    with open(path) as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "TICKETS_COVERED":
                    if isinstance(node.value, ast.List):
                        out = []
                        for elt in node.value.elts:
                            # Python 3.8+ uses ast.Constant; older 3.x exposes
                            # ast.Str. Accept both.
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                out.append(elt.value)
                            elif hasattr(ast, "Str") and isinstance(elt, ast.Str):
                                out.append(elt.s)
                        return out
    raise RuntimeError(f"TICKETS_COVERED not found in {path}")


def scan_subsumes_markers(path):
    """Return the set of ticket IDs marked `# Subsumes: <id>` in the file."""
    with open(path) as f:
        text = f.read()
    return set(re.findall(r"#\s*Subsumes:\s*([A-Z]+(?:-[A-Z]+)*-\d+)", text))


def main():
    if not os.path.isfile(BUG_FIXES):
        print(f"FAIL: {BUG_FIXES} not found (cannot read TICKETS_COVERED)", file=sys.stderr)
        return 1
    if not os.path.isfile(INVARIANTS):
        print(f"FAIL: {INVARIANTS} not found (cannot scan for Subsumes markers)", file=sys.stderr)
        return 1

    covered = set(parse_tickets_covered(BUG_FIXES))
    subsumed = scan_subsumes_markers(INVARIANTS)
    remaining = covered - subsumed

    if not remaining:
        print(
            "FAIL: every ticket in TICKETS_COVERED is now subsumed by "
            "test-policy-invariants.py — delete BOTH test-policy-bug-fixes.py "
            "AND test-historical-fixes-retirement.py (Inv 8, BACKLOG-14).",
            file=sys.stderr,
        )
        return 1

    print(
        f"ok   historical-fixes retirement watch: {len(remaining)} of "
        f"{len(covered)} ticket(s) still un-subsumed; kitchen-sink suite "
        f"may not yet be deleted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
