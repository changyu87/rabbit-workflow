#!/usr/bin/env python3
"""dispatch-spec-update.py — assemble an Opus subagent prompt for the spec-update leg.

Usage:
  dispatch-spec-update.py <feature-name> "<change-description>"

Output: assembled prompt to stdout. Caller passes stdout to Agent with model: opus.

Exit:
  0 success (prompt printed to stdout)
  1 feature not found in registry
  2 invocation error

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when spec-update is superseded by a native spec-management tool.
"""

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


def find_feature(script_dir, repo_root, feature_name):
    find_py = os.path.join(script_dir, "find-feature.py")
    result = subprocess.run(
        [sys.executable, find_py, repo_root, "lookup", feature_name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def run_policy_block(script_dir):
    policy_py = os.path.join(script_dir, "policy-block.py")
    result = subprocess.run(
        [sys.executable, policy_py],
        capture_output=True, text=True
    )
    return result.stdout


def main():
    if len(sys.argv) != 3:
        print("ERROR: usage: dispatch-spec-update.py <feature-name> <change-description>", file=sys.stderr)
        sys.exit(2)

    feature_name = sys.argv[1]
    change_desc = sys.argv[2]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = get_repo_root(script_dir)
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        sys.exit(1)

    feature_path = find_feature(script_dir, repo_root, feature_name)
    if not feature_path:
        print(f"ERROR: feature '{feature_name}' not found in registry", file=sys.stderr)
        sys.exit(1)

    feature_dir = os.path.join(repo_root, feature_path)
    spec_path = os.path.join(feature_dir, "docs", "spec", "spec.md")
    contract_path = os.path.join(feature_dir, "docs", "spec", "contract.md")
    template = os.path.join(script_dir, "..", "templates", "spec-update-template.txt")

    spec_content = "(spec.md not found)"
    if os.path.isfile(spec_path):
        with open(spec_path) as f:
            spec_content = f.read()

    contract_content = "(contract.md not found)"
    if os.path.isfile(contract_path):
        with open(contract_path) as f:
            contract_content = f.read()

    try:
        result = subprocess.run(
            ["git", "-C", repo_root, "diff", "HEAD", "--", feature_path],
            capture_output=True, text=True
        )
        lines = result.stdout.splitlines()
        git_diff = "\n".join(lines[:300]) if lines else "(no diff or git unavailable)"
    except Exception:
        git_diff = "(no diff or git unavailable)"

    template_content = "(spec-update-template.txt not found)"
    if os.path.isfile(template):
        with open(template) as f:
            template_content = f.read()

    policy_block = run_policy_block(script_dir)

    prompt = f"""{policy_block}
═══════════════════════════════════════════════════════════════════════════════
SCOPE DECLARATION
═══════════════════════════════════════════════════════════════════════════════

SCOPE: {feature_name}

You are a scoped subagent. Write ONLY inside: {feature_dir}/docs/spec/
The .rabbit-scope-active marker must be set by the caller before Agent dispatch.

═══════════════════════════════════════════════════════════════════════════════
CURRENT SPEC
═══════════════════════════════════════════════════════════════════════════════

{spec_content}

═══════════════════════════════════════════════════════════════════════════════
CURRENT CONTRACT
═══════════════════════════════════════════════════════════════════════════════

{contract_content}

═══════════════════════════════════════════════════════════════════════════════
IMPLEMENTATION DIFF SINCE LAST test-green
═══════════════════════════════════════════════════════════════════════════════

{git_diff}

═══════════════════════════════════════════════════════════════════════════════
CHANGE DESCRIPTION
═══════════════════════════════════════════════════════════════════════════════

{change_desc}

═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════

{template_content}
"""
    print(prompt, end="")
    print(f"dispatch-spec-update: prompt ready for feature '{feature_name}' — caller passes stdout to Agent with model: opus.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
