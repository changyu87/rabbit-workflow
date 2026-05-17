#!/usr/bin/env python3
# rabbit-triage.py — build a complete triage prompt for a bug filing and print to stdout.
#
# The caller captures this output, invokes an Agent with it, captures the
# TRIAGE: block from the response, and writes vet-triage.json itself.
# This script is deterministic and non-interactive.
#
# Usage:
#   rabbit-triage.py <feature-dir> <bug-name>
#
# Validates:
#   <repo-root>/.claude/bugs/<feature-name>/<bug-name>/bug.json  (required)
#   <feature-dir>/docs/spec/spec.md                              (required)
#   <feature-dir>/docs/spec/contract.md                          (optional)
#
# Bug storage uses the centralized .claude/bugs/ location as written by rabbit-file.
# <feature-name> is derived from the basename of <feature-dir>.
# <repo-root> is resolved from RABBIT_ROOT env var or git rev-parse.
#
# Exit:
#   0  prompt printed to stdout
#   1  missing required file
#   2  bad invocation
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when triage is integrated into the native bug lifecycle tool.

import os
import subprocess
import sys


def get_repo_root(script_dir):
    env_root = os.environ.get("RABBIT_ROOT")
    if env_root:
        return env_root
    try:
        result = subprocess.run(
            ["git", "-C", script_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def run_policy_block(script_dir):
    """Run policy-block.py and return its stdout."""
    policy_script = os.path.join(script_dir, "policy-block.py")
    result = subprocess.run(
        [sys.executable, policy_script],
        capture_output=True, text=True
    )
    return result.stdout


def main():
    if len(sys.argv) != 3:
        print("ERROR: usage: rabbit-triage.py <feature-dir> <bug-name>", file=sys.stderr)
        sys.exit(2)

    feature_dir = sys.argv[1]
    bug_name = sys.argv[2]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    triage_template = os.path.join(script_dir, "..", "templates", "triage-template.md")

    repo_root = get_repo_root(script_dir)
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        sys.exit(1)

    feature_basename = os.path.basename(os.path.realpath(feature_dir))
    bug_file = os.path.join(repo_root, ".claude", "bugs", feature_basename, bug_name, "bug.json")
    spec_file = os.path.join(feature_dir, "docs", "spec", "spec.md")
    contract_file = os.path.join(feature_dir, "docs", "spec", "contract.md")

    if not os.path.isdir(feature_dir):
        print(f"ERROR: feature-dir does not exist: {feature_dir}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(bug_file):
        print(f"ERROR: bug file not found: {bug_file}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(spec_file):
        print(f"ERROR: feature spec not found: {spec_file}", file=sys.stderr)
        sys.exit(1)

    with open(bug_file) as f:
        bug_content = f.read()
    with open(spec_file) as f:
        spec_content = f.read()

    if os.path.isfile(contract_file):
        with open(contract_file) as f:
            contract_content = f.read()
    else:
        contract_content = "(not present)"

    template_content = ""
    if os.path.isfile(triage_template):
        with open(triage_template) as f:
            template_content = f.read()

    # Emit policy block first.
    policy_block = run_policy_block(script_dir)
    sys.stdout.write(policy_block)

    # Assemble and print the triage prompt.
    prompt = f"""
# TRIAGE REQUEST

You are performing a one-shot read-only bug triage. You do not write files.
Produce exactly one TRIAGE: block in the format specified in the template below.

## Bug: {bug_name}
{bug_content}

## Feature spec: {feature_basename}
{spec_content}

## Feature contract (if present)
{contract_content}

## Output format (follow exactly)
{template_content}
"""
    print(prompt)
    sys.exit(0)


if __name__ == "__main__":
    main()
