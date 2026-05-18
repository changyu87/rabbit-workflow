#!/usr/bin/env python3
"""validate-feature.py — verify a feature directory against the feature-skeleton schema.

Usage: validate-feature.py <feature-dir>

Exit codes:
  0  pass
  1  validation error(s); details on stderr
  2  invocation error (bad usage, missing dir)

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when feature validation is provided natively by the rabbit CLI.
"""

import json
import os
import re
import sys


def main():
    if len(sys.argv) < 2:
        print("usage: validate-feature.py <feature-dir>", file=sys.stderr)
        sys.exit(2)

    feature_dir = sys.argv[1]

    if not feature_dir:
        print("usage: validate-feature.py <feature-dir>", file=sys.stderr)
        sys.exit(2)

    if not os.path.isdir(feature_dir):
        print(f"ERROR: not a directory: {feature_dir}", file=sys.stderr)
        sys.exit(2)

    expected_name = os.path.basename(os.path.realpath(feature_dir))
    errors = []

    def err(msg):
        print(f"ERROR: {msg}", file=sys.stderr)
        errors.append(msg)

    # Required files / dirs
    if not os.path.isfile(os.path.join(feature_dir, "feature.json")):
        err("missing feature.json")
    if not os.path.isfile(os.path.join(feature_dir, "docs", "spec", "spec.md")):
        err("missing docs/spec/spec.md")
    elif os.path.getsize(os.path.join(feature_dir, "docs", "spec", "spec.md")) == 0:
        err("docs/spec/spec.md is empty")
    if not os.path.isfile(os.path.join(feature_dir, "docs", "spec", "contract.md")):
        err("missing docs/spec/contract.md")
    elif os.path.getsize(os.path.join(feature_dir, "docs", "spec", "contract.md")) == 0:
        err("docs/spec/contract.md is empty")
    if not os.path.isdir(os.path.join(feature_dir, "docs", "bugs")):
        err("missing docs/bugs/ directory")

    run_py = os.path.join(feature_dir, "test", "run.py")
    if not os.path.isfile(run_py):
        err("missing test/run.py")
    elif not os.access(run_py, os.X_OK):
        err("test/run.py not executable")

    # Bail early if feature.json is absent or invalid JSON.
    feature_json_path = os.path.join(feature_dir, "feature.json")
    if not os.path.isfile(feature_json_path):
        print(f"FAIL: {len(errors)} error(s) in {feature_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(feature_json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        err("feature.json is not valid JSON")
        print(f"FAIL: {len(errors)} error(s) in {feature_dir}", file=sys.stderr)
        sys.exit(1)

    # Field-by-field checks.
    name = data.get("name", "")
    if not name:
        err("feature.json: missing name")
    elif name != expected_name:
        err(f"feature.json: name '{name}' does not match directory name '{expected_name}'")

    version = data.get("version", "")
    if not version:
        err("feature.json: missing version")
    elif not re.match(r"^\d+\.\d+\.\d+$", version):
        err(f"feature.json: version '{version}' is not semver (X.Y.Z)")

    owner = data.get("owner", "")
    if not owner:
        err("feature.json: missing owner")
    elif isinstance(owner, dict):
        err("feature.json: owner must be a flat string, not an object")

    tdd_state = data.get("tdd_state", "")
    valid_states = {"spec", "test-red", "impl", "test-green", "review", "merged", "deprecated"}
    if not tdd_state:
        err("feature.json: missing tdd_state")
    elif tdd_state not in valid_states:
        err(f"feature.json: invalid tdd_state '{tdd_state}' (allowed: {' | '.join(sorted(valid_states))})")

    summary = data.get("summary", "")
    if not summary:
        err("feature.json: missing summary")

    # surface must be an object with arrays: hooks, commands, agents, skills
    surface = data.get("surface")
    if not isinstance(surface, dict):
        err("feature.json: surface must be an object")
    else:
        for key in ("hooks", "commands", "agents", "skills"):
            if not isinstance(surface.get(key), list):
                err(f"feature.json: surface.{key} must be an array")

    criterion = data.get("deprecation_criterion", "")
    if not criterion:
        err("feature.json: missing deprecation_criterion")

    if errors:
        print(f"FAIL: {len(errors)} error(s) in {feature_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"PASS: {feature_dir}")
    sys.exit(0)


if __name__ == "__main__":
    main()
