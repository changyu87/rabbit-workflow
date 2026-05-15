#!/usr/bin/env python3
# dispatch-feature-tdd.py — assemble the prompt for a per-feature full-TDD-cycle subagent.
#
# Usage:
#   dispatch-feature-tdd.py <feature-name> "<request-description>" [--linked-item <dir> --item-type <bug|backlog>]
#
# Output: assembled prompt to stdout. Caller passes stdout to Agent.
# The subagent runs spec-update -> test-red -> impl -> test-green for the named feature,
# then writes tdd-report.json to .rabbit/tdd-report.json. The calling skill handles status updates.
#
# Optional flags:
#   --linked-item <dir>   Directory of the linked bug or backlog item.
#   --item-type <type>    Required with --linked-item: bug|backlog
#
# Version: 2.0.0
# Owner: rabbit-workflow team (tdd-state-machine)
# Deprecation criterion: when the TDD cycle is natively supported by the dispatch infrastructure.

import os
import subprocess
import sys


def _repo_root(script_dir):
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "-C", script_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def main(argv):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = _repo_root(script_dir)

    if len(argv) < 2:
        sys.stderr.write(
            "ERROR: usage: dispatch-feature-tdd.py <feature-name> <request-description> "
            "[--linked-item <dir> --item-type <bug|backlog>]\n"
        )
        return 2

    feature_name = argv[0]
    request = argv[1]
    rest = argv[2:]

    linked_item_dir = ""
    item_type = ""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--linked-item":
            if i + 1 >= len(rest) or not rest[i + 1]:
                sys.stderr.write("ERROR: --linked-item requires a directory argument\n")
                return 2
            linked_item_dir = rest[i + 1]
            i += 2
        elif a == "--item-type":
            if i + 1 >= len(rest) or not rest[i + 1]:
                sys.stderr.write("ERROR: --item-type requires bug|backlog\n")
                return 2
            item_type = rest[i + 1]
            i += 2
        elif a in ("--bug", "--backlog"):
            sys.stderr.write(
                f"ERROR: {a} is removed. Use --linked-item <dir> --item-type <bug|backlog>\n"
            )
            return 2
        else:
            sys.stderr.write(f"ERROR: unknown argument: {a}\n")
            return 2

    if linked_item_dir and not item_type:
        sys.stderr.write("ERROR: --linked-item requires --item-type <bug|backlog>\n")
        return 2
    if item_type and not linked_item_dir:
        sys.stderr.write("ERROR: --item-type requires --linked-item <dir>\n")
        return 2

    find_feature = os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "find-feature.py"
    )
    try:
        res = subprocess.run(
            [sys.executable, find_feature, repo_root, "lookup", feature_name],
            capture_output=True, text=True, check=False,
        )
        if res.returncode != 0:
            sys.stderr.write(f"ERROR: feature '{feature_name}' not found\n")
            return 1
        feature_path = res.stdout.strip()
        if not feature_path:
            sys.stderr.write(f"ERROR: feature '{feature_name}' not found\n")
            return 1
    except Exception:
        sys.stderr.write(f"ERROR: feature '{feature_name}' not found\n")
        return 1

    feature_dir = os.path.join(repo_root, feature_path)
    spec_path = os.path.join(feature_dir, "docs", "spec", "spec.md")
    contract_path = os.path.join(feature_dir, "docs", "spec", "contract.md")

    spec_content = "(spec.md not found)"
    if os.path.isfile(spec_path):
        try:
            with open(spec_path, "r") as f:
                spec_content = f.read()
        except Exception:
            pass

    contract_content = "(contract.md not found)"
    if os.path.isfile(contract_path):
        try:
            with open(contract_path, "r") as f:
                contract_content = f.read()
        except Exception:
            pass

    policy_block_py = os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "policy-block.py"
    )
    policy_block = ""
    if os.path.isfile(policy_block_py):
        try:
            res = subprocess.run(
                [sys.executable, policy_block_py],
                capture_output=True, text=True, check=False,
            )
            if res.returncode == 0:
                policy_block = res.stdout
                # Match shell behavior: $(...) strips trailing newlines.
                policy_block = policy_block.rstrip("\n")
        except Exception:
            pass

    dispatch_spec_sh = os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "dispatch-spec-update.py"
    )
    dispatch_edit_sh = os.path.join(
        repo_root, ".claude", "features", "contract", "scripts", "dispatch-feature-edit.py"
    )
    tdd_step_py = os.path.join(
        repo_root, ".claude", "features", "tdd-state-machine", "scripts", "tdd-step.py"
    )

    linked_item_value = linked_item_dir if linked_item_dir else "null"
    item_type_value = item_type if item_type else "null"

    prompt = f"""RABBIT-POLICY-BLOCK-v1
{policy_block}

════════════════════════════════════════════════════════════════════════
SCOPE DECLARATION
════════════════════════════════════════════════════════════════════════

SCOPE: {feature_name}

You are a per-feature TDD orchestrator subagent. You run the FULL TDD cycle
(spec-update → test-red → impl → test-green) for the feature declared above.

You use the per-feature scope marker for parallel-safe operation:
  touch {repo_root}/.rabbit-scope-active-{feature_name}

Set this marker as your FIRST action. Remove it as your LAST action (trap EXIT).
This enables parallel dispatch alongside agents for other features.

════════════════════════════════════════════════════════════════════════
REQUEST
════════════════════════════════════════════════════════════════════════

{request}

════════════════════════════════════════════════════════════════════════
FEATURE SPEC
════════════════════════════════════════════════════════════════════════

{spec_content}

════════════════════════════════════════════════════════════════════════
FEATURE CONTRACT
════════════════════════════════════════════════════════════════════════

{contract_content}

════════════════════════════════════════════════════════════════════════
TDD CYCLE — EXECUTE IN ORDER
════════════════════════════════════════════════════════════════════════

Step 0: Set scope marker
  touch {repo_root}/.rabbit-scope-active-{feature_name}
  trap 'rm -f {repo_root}/.rabbit-scope-active-{feature_name}' EXIT

Step 1: Force to spec-update
  python3 {tdd_step_py} transition {feature_dir} spec-update --force

Step 2: Dispatch SPEC-UPDATE subagent (Opus — R2)
  PROMPT=$(python3 {dispatch_spec_sh} {feature_name} "<summarize what the request requires>")
  Dispatch Agent(model: opus, prompt: PROMPT)
  Read HANDOFF — verify spec_changes field present.

Step 3: Read spec git diff
  git diff HEAD -- {feature_dir}/docs/spec/

Step 4: Advance to test-red
  python3 {tdd_step_py} transition {feature_dir} test-red
  (or with --spec-no-change-reason "<reason>" if spec was unchanged)

Step 5: Dispatch TEST subagent
  PROMPT=$(python3 {dispatch_edit_sh} {feature_name} "Write failing tests only. Assert spec invariants. Do NOT implement. Run tests, confirm they fail.")
  Dispatch Agent(prompt: PROMPT)
  Read HANDOFF — verify test_result: fail.

Step 6: Advance to impl
  python3 {tdd_step_py} transition {feature_dir} impl

Step 7: Dispatch IMPLEMENTATION subagent
  PROMPT=$(python3 {dispatch_edit_sh} {feature_name} "Implement to make tests pass. Follow spec invariants. Run all tests, confirm pass. Then: python3 {tdd_step_py} transition {feature_dir} test-green")
  Dispatch Agent(prompt: PROMPT)

Step 7b: Inline spec-review (performed by you — do NOT dispatch another Agent)
  Read: {spec_path}
  Run:  git diff HEAD -- {feature_dir}/
  Compare each spec invariant to the implementation diff.
  Produce two values:
    spec_compliance: "pass" if all invariants addressed, "fail" if any are missing
    spec_compliance_notes: list any unaddressed invariants, or null if pass

Step 8: Write tdd-report.json to .rabbit/ (gitignored — NEVER commit this file)
  mkdir -p {repo_root}/.rabbit/
  Path: {repo_root}/.rabbit/tdd-report.json
  Write exactly this JSON schema:
  {{
    "schema_version": "1.0.0",
    "feature": "{feature_name}",
    "request": "<original request text>",
    "linked_item": "{linked_item_value}",
    "item_type": "{item_type_value}",
    "spec_changes": "<yes|no>",
    "spec_no_change_reason": "<reason or null>",
    "test_gap_analysis": "<what was missing in test coverage before this fix, or 'none'>",
    "impl_summary": "<one paragraph describing what was implemented>",
    "spec_compliance": "<pass|fail>",
    "spec_compliance_notes": "<unaddressed invariants or null>",
    "test_result": "pass",
    "tdd_state": "test-green",
    "impl_commit": "<output of: git rev-parse HEAD>"
  }}

Step 9: Scope marker removed by trap (EXIT fires automatically)

════════════════════════════════════════════════════════════════════════
HANDOFF (emit when complete)
════════════════════════════════════════════════════════════════════════

HANDOFF:
  feature: {feature_name}
  tdd_state: test-green
  test_result: pass
  spec_compliance: <pass|fail>
  tdd_report_path: {repo_root}/.rabbit/tdd-report.json
  notes: <brief summary>

"""
    sys.stdout.write(prompt)
    sys.stderr.write(f"dispatch-feature-tdd: prompt ready for feature '{feature_name}'\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
