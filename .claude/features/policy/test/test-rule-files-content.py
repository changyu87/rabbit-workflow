#!/usr/bin/env python3
"""test-rule-files-content.py — Spot-checks content of the three rule files.

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when the rule-file content is enforced by a richer
schema-driven check (e.g., declarative section manifest).
"""
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def check_phrase(file, phrase):
    path = os.path.join(FEATURE_DIR, file)
    with open(path) as f:
        content = f.read()
    if phrase not in content:
        print(f"FAIL: '{phrase}' not found in {path}", file=sys.stderr)
        sys.exit(1)


def check_phrase_absent(file, phrase):
    path = os.path.join(FEATURE_DIR, file)
    with open(path) as f:
        content = f.read()
    if phrase in content:
        print(f"FAIL: '{phrase}' should NOT be in {path} but was found", file=sys.stderr)
        sys.exit(1)


def check_first_heading(file, expected):
    path = os.path.join(FEATURE_DIR, file)
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                actual = line.rstrip("\n")
                if actual != expected:
                    print(
                        f"FAIL: first heading in {path} is '{actual}', expected '{expected}'",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                return
    print(f"FAIL: no heading found in {path}", file=sys.stderr)
    sys.exit(1)


# spec-rules.md
check_phrase("spec-rules.md", "Tool-Choice Tier")
check_phrase("spec-rules.md", "Schemas and Contracts")
check_phrase("spec-rules.md", "Lifecycle and Ownership")

# Issue #439: spec-rules.md establishes the SKILL.md Authoring Standard with
# three citable rules deriving from the existing policy principles.
check_phrase("spec-rules.md", "SKILL.md Authoring Standard")
# Rule 1 — orchestration logic is script-backed, not prompt-tier placeholders.
check_phrase("spec-rules.md", "Script-Backed Orchestration")
# Rule 2 — policy is embedded verbatim from the canonical source, not paraphrased.
check_phrase("spec-rules.md", "Verbatim Policy Embedding")
# Rule 3 — SKILL.md changes are validated through skill-creator before deployment.
check_phrase("spec-rules.md", "skill-creator Validation")

# Inv 13: the SKILL.md Authoring Standard carries the no-nesting rule — a
# subagent-dispatching skill MUST NOT be invoked inside an Agent() call (illegal
# two-level nesting). Parallelize by dispatching the underlying subagent at
# level 1, not by wrapping the skill in parallel Agent() calls.
check_phrase("spec-rules.md", "No Subagent-Dispatching Skill Inside `Agent()`")
check_phrase("spec-rules.md", "MUST NOT itself be invoked inside an")
check_phrase("spec-rules.md", "illegal two-level nesting")
check_phrase("spec-rules.md", "main → N parallel subagents")
check_phrase("spec-rules.md", "rabbit-spec-create")
check_phrase("spec-rules.md", "rabbit-feature-touch")
# Issue #690: rabbit-feature-scope is the THIRD subagent-dispatching skill —
# it dispatches an UNTYPED default-model Agent (`Agent(prompt=...)`, no
# subagent_type). The named set MUST include it, and the rule MUST cover
# untyped dispatches, not only `Agent(subagent_type=...)` ones.
check_phrase("spec-rules.md", "rabbit-feature-scope")
check_phrase("spec-rules.md", "Agent(prompt=...)")
check_phrase("spec-rules.md", "any future subagent-dispatching skill inherits")
# History-free: the rule text must not carry issue/PR refs.
check_phrase_absent("spec-rules.md", "#647")

# Issue #416 (Part A): §3 Owner bullet mandates `rabbit-workflow team` for
# repo-level features distributed as part of rabbit-workflow; individual
# ownership is reserved for personal/experimental/out-of-distribution artifacts.
check_phrase(
    "spec-rules.md",
    "For repo-level features distributed as part of rabbit-workflow, the owner MUST be `rabbit-workflow team`, not an individual.",
)
check_phrase(
    "spec-rules.md",
    "Individual ownership is reserved for personal scripts, experimental tooling, and out-of-distribution artifacts.",
)

# coding-rules.md
check_phrase("coding-rules.md", "Think Before Coding")
check_phrase("coding-rules.md", "Simplicity First")
check_phrase("coding-rules.md", "Karpathy")

# Inv 6: Read-before-Edit canonical phrase must appear in coding-rules.md.
# Phrase propagates rabbit-feature's spec-edit Read-before-Edit obligation via
# the policy preamble.
check_phrase(
    "coding-rules.md",
    "Before editing an existing file, Read it. Before writing alongside existing code, Read the surrounding module. Edits made without reading are speculative.",
)

# Inv 12: prove-it-dead-or-flag cleanup methodology. coding-rules.md MUST carry
# the cleanup definition-of-done rule with VERIFICATION-driven checks, the
# three-row action table, and the annotate-and-continue discipline.
check_phrase("coding-rules.md", "Prove It Dead or Flag It")
check_phrase("coding-rules.md", "never silently keep")
# The four verification check kinds.
check_phrase("coding-rules.md", "path reference")
check_phrase("coding-rules.md", "`find`")
check_phrase("coding-rules.md", "`grep`")
check_phrase("coding-rules.md", "reachable code path")
check_phrase("coding-rules.md", "cross-feature claim")
# The three-row action table actions.
check_phrase("coding-rules.md", "Proven dead")
check_phrase("coding-rules.md", "Proven live")
check_phrase("coding-rules.md", "Unverifiable")
check_phrase("coding-rules.md", "`housekeeping`")
# Annotate-and-continue.
check_phrase("coding-rules.md", "Annotate-and-continue")
check_phrase("coding-rules.md", "the pass CONTINUES")
check_phrase("coding-rules.md", "One uncertain sentence never stalls a")
# History-free: the rule text must not carry issue/PR refs or tombstone words.
check_phrase_absent("coding-rules.md", "#639")

# philosophy.md
check_phrase("philosophy.md", "Machine First")
check_phrase("philosophy.md", "Bounded Scope")
check_phrase("philosophy.md", "Designed Deprecation")

# CHANGE B — philosophy.md heading hierarchy fixed
# t_phil_h1: philosophy.md first non-empty line is "# Philosophy" (H1, not H2)
check_first_heading("philosophy.md", "# Philosophy")

# t_phil_no_h2: philosophy.md does NOT contain "## Philosophy" (the old H2)
check_phrase_absent("philosophy.md", "## Philosophy")

# t_phil_subsections: philosophy.md subsections use ## (H2), not ### (H3)
check_phrase("philosophy.md", "## 1. Machine First")

print("All checks passed.")
