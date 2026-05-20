#!/usr/bin/env python3
"""dispatch-feature-edit.py — the only legal Agent dispatch path for feature edits.

Usage:
  dispatch-feature-edit.py [--bug <bug-dir>] <feature-name> <task-description>

Uses find-feature.py to locate the feature root, sets a scope marker, builds
the policy block, and prints the assembled prompt to stdout. The caller
passes stdout as the prompt field to an Agent call. This script never
invokes Agent directly — keeping it deterministic and testable.

Exit:
  0 success (prompt printed to stdout)
  1 feature not found in registry
  2 invocation error

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when feature dispatch is handled natively by the rabbit CLI.
"""

import json
import os
import signal
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
    # Strip the sentinel line (first line).
    lines = result.stdout.splitlines(keepends=True)
    if lines and lines[0].strip() == "RABBIT-POLICY-BLOCK-v1":
        return "".join(lines[1:])
    return result.stdout


def build_tdd_gap_reflection(bug_dir, bug_id, bug_title):
    return f"""\
═══════════════════════════════════════════════════════════════════════════════
TDD-GAP REFLECTION — MANDATORY FOR BUG FIXES
═══════════════════════════════════════════════════════════════════════════════

Bug: {bug_id} — {bug_title}

A bug reaching open status means the test suite did not catch it. Fixing
the symptom without closing the test gap is incomplete work — the same class
of regression will land again.

Before you may emit your final HANDOFF, you MUST:

  1. Identify the test that SHOULD have caught this bug.
       - If a test existed but did not exercise the failing path, name it.
       - If no test existed for this behavior, state: "none existed."

  2. Add (or extend) a test under the feature's test/ that fails against
     the un-fixed code and passes against your fix. Name the test after
     the bug id (e.g. test-{bug_id}-<description>.py).

  3. Verify both directions:
       - Without your fix: the new test MUST fail.
       - With your fix:    the new test MUST pass.

  4. Include a TDD_GAP: block inside your HANDOFF (see handoff template).

If the bug is genuinely untestable, set existed: untestable and explain.
"Hard to test" is not "untestable." Main session will refuse a HANDOFF
that omits TDD_GAP for a bug-fix dispatch.
"""


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    bug_dir = ""
    args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--bug":
            if i + 1 >= len(sys.argv):
                print("ERROR: --bug requires a path arg", file=sys.stderr)
                sys.exit(2)
            bug_dir = sys.argv[i + 1]
            i += 2
        else:
            args.append(sys.argv[i])
            i += 1

    if len(args) < 2:
        print("ERROR: usage: dispatch-feature-edit.py [--bug <bug-dir>] <feature-name> <task-description>", file=sys.stderr)
        sys.exit(2)

    feature_name = args[0]
    task_desc = args[1]

    repo_root = get_repo_root(script_dir)
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        sys.exit(1)

    feature_path = find_feature(script_dir, repo_root, feature_name)
    if not feature_path:
        print(f"ERROR: feature '{feature_name}' not found", file=sys.stderr)
        sys.exit(1)

    # Build TDD_GAP_REFLECTION if --bug was provided.
    tdd_gap_reflection = ""
    if bug_dir:
        if not os.path.isdir(bug_dir):
            print(f"ERROR: --bug dir not found: {bug_dir}", file=sys.stderr)
            sys.exit(2)
        bug_json_path = os.path.join(bug_dir, "bug.json")
        if not os.path.isfile(bug_json_path):
            print(f"ERROR: --bug dir missing bug.json: {bug_dir}", file=sys.stderr)
            sys.exit(2)
        try:
            with open(bug_json_path) as f:
                bug_data = json.load(f)
            bug_id = bug_data.get("id") or bug_data.get("bug_id") or "unknown"
            bug_title = bug_data.get("title") or bug_data.get("summary") or "unknown"
        except Exception:
            bug_id = "unknown"
            bug_title = "unknown"
        tdd_gap_reflection = build_tdd_gap_reflection(bug_dir, bug_id, bug_title)

    # Detect if this is a project feature.
    #
    # Rabbit-level features live under ".claude/features/<name>/".
    # Project-level features live under "<project_root>/features/<name>/"
    # where <project_root> is a top-level directory other than ".claude".
    #
    # The previous heuristic — `parts[1] == "features"` — misfired on rabbit
    # paths like ".claude/features/contract" (parts[1] is "features", and the
    # script would then look for `<repo>/.claude/contract`, which doesn't exist).
    # We discriminate explicitly: rabbit if the path starts with ".claude/features/",
    # project if it matches "<top>/features/<name>" with top != ".claude".
    project_contract_content = ""
    norm = feature_path.replace(os.sep, "/")
    if not norm.startswith(".claude/features/"):
        parts = feature_path.split(os.sep)
        if len(parts) >= 2 and parts[1] == "features" and parts[0] != ".claude":
            project_root = parts[0]
            proj_contract_dir = os.path.join(repo_root, project_root, "contract")
            if os.path.isdir(proj_contract_dir):
                import glob
                mds = sorted(glob.glob(os.path.join(proj_contract_dir, "*.md")))
                for md in mds:
                    with open(md) as f:
                        project_contract_content += f.read()

    scope_marker = os.path.join(repo_root, ".rabbit-scope-active")

    def cleanup():
        try:
            os.remove(scope_marker)
        except FileNotFoundError:
            pass

    # Register cleanup for signals.
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: (cleanup(), sys.exit(1)))

    with open(scope_marker, "w") as f:
        f.write(feature_name)

    try:
        policy_block = run_policy_block(script_dir)

        feature_dir = os.path.join(repo_root, feature_path)
        spec_path = os.path.join(feature_dir, "docs", "spec", "spec.md")
        contract_path = os.path.join(feature_dir, "docs", "spec", "contract.md")

        feature_spec = ""
        if os.path.isfile(spec_path):
            with open(spec_path) as f:
                feature_spec = f.read()

        feature_contract = ""
        if os.path.isfile(contract_path):
            with open(contract_path) as f:
                feature_contract = f.read()

        template_path = os.path.join(script_dir, "..", "templates", "subagent-launch-template.txt")
        if os.path.isfile(template_path):
            with open(template_path) as f:
                prompt_text = f.read()
            prompt_text = prompt_text.replace("{{POLICY_BLOCK}}", policy_block)
            prompt_text = prompt_text.replace("{{feature_name}}", feature_name)
            prompt_text = prompt_text.replace("{{task_description}}", task_desc)
            prompt_text = prompt_text.replace("{{tdd_gap_reflection}}", tdd_gap_reflection)
            prompt_text = prompt_text.replace("{{feature_spec}}", feature_spec)
            prompt_text = prompt_text.replace("{{feature_contract}}", feature_contract)
            prompt_text = prompt_text.replace("{{project_contract}}", project_contract_content)
            print(prompt_text)
        else:
            # Fallback inline prompt.
            print(f"RABBIT-POLICY-BLOCK-v1")
            print(policy_block)
            print()
            print("═" * 79)
            print("SCOPE DECLARATION")
            print("═" * 79)
            print()
            print(f"SCOPE: {feature_name}")
            print()
            print("═" * 79)
            print("TASK")
            print("═" * 79)
            print()
            print(task_desc)
            print()
            if tdd_gap_reflection:
                print(tdd_gap_reflection)
            print("═" * 79)
            print("FEATURE SPEC")
            print("═" * 79)
            print()
            print(feature_spec)
            print()
            print("═" * 79)
            print("FEATURE CONTRACT")
            print("═" * 79)
            print()
            print(feature_contract)

        print(f"dispatch-feature-edit: prompt ready for feature '{feature_name}' — caller passes stdout to Agent.", file=sys.stderr)
    finally:
        cleanup()

    sys.exit(0)


if __name__ == "__main__":
    main()
