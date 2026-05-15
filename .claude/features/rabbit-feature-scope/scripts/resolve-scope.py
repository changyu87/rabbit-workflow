#!/usr/bin/env python3
# resolve-scope.py — build a prompt that maps a request to affected rabbit features.
#
# Usage:
#   resolve-scope.py "<request-description>"
#
# Output: assembled prompt to stdout. Caller dispatches with default model.
# Agent response JSON: {"features": ["feat-a"], "rationale": "one sentence"}
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-feature-scope)
# Deprecation criterion: when feature-scope resolution is automated by the dispatch infrastructure.

import os
import subprocess
import sys

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.environ.get("RABBIT_ROOT")
    if not repo_root:
        try:
            repo_root = subprocess.check_output(
                ["git", "-C", script_dir, "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except subprocess.CalledProcessError:
            repo_root = ""

    find_feature = os.path.join(repo_root, ".claude/features/contract/scripts/find-feature.py")

    if len(sys.argv) != 2:
        print("ERROR: usage: resolve-scope.py <request-description>", file=sys.stderr)
        sys.exit(2)

    request = sys.argv[1]

    if not os.path.isfile(find_feature):
        print(f"ERROR: find-feature.py not found: {find_feature}", file=sys.stderr)
        sys.exit(1)

    format_script = os.path.join(script_dir, "format-feature-context.py")

    try:
        list_json = subprocess.check_output(
            ["python3", find_feature, repo_root, "list-json"],
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        list_json = b"[]"

    try:
        feature_context = subprocess.check_output(
            ["python3", format_script],
            input=list_json,
            stderr=subprocess.DEVNULL
        ).decode()
    except subprocess.CalledProcessError:
        feature_context = ""

    prompt = f"""You are a feature-scope resolver for a rabbit-workflow repository.

Given a natural-language request, identify which features the request targets.
A request targets a feature if the implementation work will modify files within
that feature's directory.

REGISTERED FEATURES:
{feature_context}

REQUEST:
{request}

Respond with ONLY valid JSON on a single line — no markdown, no explanation:
{{"features": ["feature-name-1", "feature-name-2"], "rationale": "one sentence"}}

Rules:
- Include a feature only if the request requires writing/editing files in that feature's directory.
- If the request touches cross-cutting infrastructure (dispatch scripts, schemas, enforcement), include "contract".
- If the request touches hooks, commands, or skills surface, include "rabbit-cage".
- Omit features whose files will not be modified.
- Return an empty features list [] if no features are targeted."""

    print(prompt)


if __name__ == "__main__":
    main()
