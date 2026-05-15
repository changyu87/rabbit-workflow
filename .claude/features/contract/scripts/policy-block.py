#!/usr/bin/env python3
# policy-block.py — emit the canonical rabbit-workflow policy block to stdout.
#
# This block is the MANDATORY prepend for every Agent dispatch (rabbit's own
# subagents AND Claude's built-in ones). The dispatcher captures stdout and
# prepends to the prompt field of the Agent tool call. Per hard-rules R6.
#
# Usage:
#   policy-block.py                                # philosophy.md + spec-rules.md + coding-rules.md
#   policy-block.py --include <path>               # plus the named file
#   policy-block.py --include a --include b ...    # multiple includes compose
#
# Files are looked up at:
#   <repo>/.claude/features/policy/philosophy.md
#   <repo>/.claude/features/policy/spec-rules.md
#   <repo>/.claude/features/policy/coding-rules.md
# where <repo> is computed from this script's location.
#
# Exit:
#   0 success
#   1 a --include path is missing
#   2 invocation error
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when policy injection is handled natively by the dispatch infrastructure.

import os
import subprocess
import sys


def get_repo_root():
    env_root = os.environ.get("RABBIT_ROOT")
    if env_root:
        return env_root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        result = subprocess.run(
            ["git", "-C", script_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def parse_args(argv):
    includes = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg == "--include":
            if i + 1 >= len(argv):
                print("ERROR: --include requires a path arg", file=sys.stderr)
                sys.exit(2)
            includes.append(argv[i + 1])
            i += 2
        else:
            print(f"ERROR: unknown arg '{arg}'", file=sys.stderr)
            sys.exit(2)
    return includes


def print_usage():
    print(__doc__, file=sys.stderr)


def emit_section(label, path):
    sep = "─" * 18
    print(f"{sep} {label} {sep}")
    with open(path) as f:
        print(f.read())


def main():
    includes = parse_args(sys.argv[1:])

    repo_root = get_repo_root()
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        sys.exit(1)

    policy_dir = os.path.join(repo_root, ".claude", "features", "policy")
    phil = os.path.join(policy_dir, "philosophy.md")
    spec_rules = os.path.join(policy_dir, "spec-rules.md")
    coding_rules = os.path.join(policy_dir, "coding-rules.md")

    # Validate --include paths upfront.
    for p in includes:
        if not os.path.isfile(p):
            print(f"ERROR: --include path does not exist: {p}", file=sys.stderr)
            sys.exit(1)

    # Sanity: canonical files must exist.
    for f in (phil, spec_rules, coding_rules):
        if not os.path.isfile(f):
            print(f"ERROR: missing canonical policy file: {f}", file=sys.stderr)
            sys.exit(1)

    # Emit sentinel line.
    print("RABBIT-POLICY-BLOCK-v1")

    # Emit block header.
    header = """\
═══════════════════════════════════════════════════════════════════════════════
MANDATORY POLICY — READ THIS BEFORE ANY ACTION
═══════════════════════════════════════════════════════════════════════════════

You are operating within the rabbit workflow. The following policy files are
NOT optional reading. They govern every choice you make in this invocation.
Failure to comply is a constitution violation.

If you have not yet internalized these principles, STOP and read them now
before doing anything else. Re-read them whenever you are uncertain about
how to proceed. They are the source of truth for every decision in this
session.
"""
    print(header)

    emit_section("philosophy.md", phil)
    emit_section("spec-rules.md", spec_rules)
    emit_section("coding-rules.md", coding_rules)

    for p in includes:
        emit_section(os.path.basename(p), p)

    footer = """\
═══════════════════════════════════════════════════════════════════════════════
END POLICY — internalize the above, then proceed. Every action must reflect it.
═══════════════════════════════════════════════════════════════════════════════"""
    print(footer)
    sys.exit(0)


if __name__ == "__main__":
    main()
