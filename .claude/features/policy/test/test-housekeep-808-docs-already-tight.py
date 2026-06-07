#!/usr/bin/env python3
"""test-housekeep-808-docs-already-tight.py — issue #808 (child of #794).

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when a cross-feature housekeeping harness lints the
canonical rule files against an authoritative content manifest, making this
per-feature verified-and-kept assertion redundant.

Traces: #808

End-to-end regression guard recording the outcome of the #808 measured
verify-or-flag reduction wave (coding-rules §6 prove-it-dead-or-flag, §2
Simplicity First, §7 Parenthetical Clarity).

The wave's honest measured result was ZERO normative prose removed: the three
canonical rule files are normative governance documents injected wholesale into
the repo CLAUDE.md and cited verbatim by other features, so every clause is
load-bearing. This test reads the rule files exactly as a consumer would and
asserts that the specific load-bearing EXEMPLARS the wave verified-and-kept are
still present — so a future over-zealous reduction pass cannot silently delete
them and stay green. It also asserts the CHANGELOG records the #808 wave (the
machine-readable provenance for the verified-and-kept decision).

Non-interactive. Exits non-zero on failure.
"""
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def read(rel):
    with open(os.path.join(FEATURE_DIR, rel)) as f:
        return f.read()


coding_rules = read("coding-rules.md")
spec_rules = read("spec-rules.md")
philosophy = read("philosophy.md")
changelog = read(os.path.join("docs", "CHANGELOG.md"))

# §7 Parenthetical Clarity: the load-bearing CITATION exemplar the rule itself
# names as keep-inline must survive verbatim. The #808 wave verified this is
# load-bearing (a precise citation token), not decorative, and KEPT it.
for name, body, phrase in [
    ("cite-inv49", coding_rules, "a citation like `(Inv 49)`"),
    # §7 names code tokens as a keep-inline class; this is the canonical token.
    ("code-token", spec_rules, "`Agent(prompt=...)`"),
    # §1 Tool-Choice Tier load-bearing read-only-command exemplar.
    ("readonly-cmd", spec_rules, "`git log --oneline -5`"),
    # philosophy §1 load-bearing rhetorical definition of silent drift.
    ("drift-def", philosophy, 'why did it do that?'),
    # philosophy §2 load-bearing contract-block code token.
    ("contract-block", philosophy, "`provides` / `reads` / `invokes` / `never`"),
]:
    if phrase in body:
        ok(name, f"verified-and-kept exemplar present: {phrase!r}")
    else:
        fail(name, f"load-bearing exemplar removed (regression): {phrase!r}")

# Machine-readable provenance: the CHANGELOG records the #808 verify-or-flag
# wave and its honest zero-removal result.
if "#808" in changelog:
    ok("changelog-ref", "CHANGELOG records the #808 wave")
else:
    fail("changelog-ref", "CHANGELOG does not record the #808 wave")
if "v1.21.0" in changelog:
    ok("changelog-version", "CHANGELOG carries the v1.21.0 entry")
else:
    fail("changelog-version", "CHANGELOG missing the v1.21.0 entry")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-housekeep-808-docs-already-tight: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-housekeep-808-docs-already-tight: all checks passed.")
sys.exit(0)
