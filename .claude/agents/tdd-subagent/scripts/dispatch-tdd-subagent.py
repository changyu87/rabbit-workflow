#!/usr/bin/env python3
# dispatch-tdd-subagent.py — assembles the prompt for a per-feature TDD subagent.
#
# Usage:
#   dispatch-tdd-subagent.py \
#     --scope <feature-name> \
#     --spec <spec-path> \
#     [--impl-suggestion <path>] \
#     [--linked-item <dir>] \
#     [--item-type bug|backlog] \
#     [--no-human-approval] \
#     [--code-review-full-loop] \
#     [--max-iterations N]
#
# Output: assembled prompt to stdout. Caller: Agent(model: opus, prompt: stdout).
# Version: 2.0.0
# Owner: rabbit-workflow team (tdd-subagent)
# Deprecation criterion: when TDD cycle is natively supported by rabbit CLI.

import argparse
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


def _read_file(path, default="(not found)"):
    if path and os.path.isfile(path):
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            pass
    return default


def _policy_block(repo_root):
    py = os.path.join(repo_root, ".claude", "features", "contract", "scripts", "policy-block.py")
    if not os.path.isfile(py):
        return ""
    try:
        res = subprocess.run([sys.executable, py], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return res.stdout.rstrip("\n")
    except Exception:
        pass
    return ""


def _find_feature(repo_root, feature_name):
    find_py = os.path.join(repo_root, ".claude", "features", "contract", "scripts", "find-feature.py")
    try:
        res = subprocess.run(
            [sys.executable, find_py, repo_root, "lookup", feature_name],
            capture_output=True, text=True, check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def main(argv):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = _repo_root(script_dir)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--impl-suggestion", default=None)
    parser.add_argument("--linked-item", default=None)
    parser.add_argument("--item-type", default=None, choices=["bug", "backlog"])
    parser.add_argument("--no-human-approval", action="store_true")
    parser.add_argument("--code-review-full-loop", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=3)

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        sys.stderr.write(
            "ERROR: usage: dispatch-tdd-subagent.py --scope <feature> --spec <path> "
            "[--impl-suggestion <path>] [--linked-item <dir>] [--item-type bug|backlog] "
            "[--no-human-approval] [--code-review-full-loop] [--max-iterations N]\n"
        )
        return 2

    if args.linked_item and not args.item_type:
        sys.stderr.write("ERROR: --linked-item requires --item-type\n")
        return 2
    if args.item_type and not args.linked_item:
        sys.stderr.write("ERROR: --item-type requires --linked-item\n")
        return 2
    if args.max_iterations < 1:
        sys.stderr.write("ERROR: --max-iterations must be >= 1\n")
        return 2

    feature_name = args.scope
    feature_path = _find_feature(repo_root, feature_name)
    if not feature_path:
        sys.stderr.write(f"ERROR: feature '{feature_name}' not found\n")
        return 1

    feature_dir = os.path.join(repo_root, feature_path)
    tdd_step_py = os.path.join(repo_root, ".claude", "features", "tdd-subagent", "scripts", "tdd-step.py")

    spec_content = _read_file(args.spec)
    impl_suggestion_block = ""
    if args.impl_suggestion:
        raw = _read_file(args.impl_suggestion)
        if raw != "(not found)":
            impl_suggestion_block = f"\n## Implementation Suggestion\n\n```json\n{raw}\n```\n"

    policy_block = _policy_block(repo_root)
    linked_item_value = args.linked_item or "null"
    item_type_value = args.item_type or "null"

    if args.no_human_approval:
        human_approval_section = (
            "\n## Step 2 — HUMAN-APPROVAL\n\nSkipped (--no-human-approval).\n"
        )
    else:
        human_approval_section = """
## Step 2 — HUMAN-APPROVAL

Invoke `Skill("superpowers:writing-plans")` to produce an implementation summary with:
- Key implementation points (bullet list)
- Affected files (explicit paths)

Present this summary to the user and wait for explicit approval before Step 3 (LOCK).
If the user requests changes, update and re-present. Do NOT proceed without approval.
"""

    if args.code_review_full_loop:
        code_review_loop_note = (
            "--code-review-full-loop is active: after any code changes from CODE-REVIEW, "
            "loop back to Step 4 (TEST-WRITE) and repeat until CODE-REVIEW produces no further changes."
        )
    else:
        code_review_loop_note = (
            "Default mode: use judgment — loop back to Step 4 (TEST-WRITE) only if "
            "CODE-REVIEW changed functional code or tests. HUMAN-APPROVAL (Step 2) does NOT re-run on loop-back."
        )

    prompt = f"""{policy_block}

════════════════════════════════════════════════════════════════════════
TDD SUBAGENT — SCOPE: {feature_name}
════════════════════════════════════════════════════════════════════════

You are a TDD subagent. Execute the 9 named steps below IN ORDER for feature: {feature_name}
Do NOT skip steps. Do NOT dispatch nested subagents. All work is done inline.

════════════════════════════════════════════════════════════════════════
SPEC
════════════════════════════════════════════════════════════════════════

{spec_content}
{impl_suggestion_block}
════════════════════════════════════════════════════════════════════════
E2E TEST RULE (non-negotiable)
════════════════════════════════════════════════════════════════════════

Every behaviour described in the spec MUST have a corresponding end-to-end test.
Unit tests alone are insufficient. If a spec behaviour has no e2e test, add one in TEST-WRITE.
This rule applies to ALL TDD cycles without exception.

════════════════════════════════════════════════════════════════════════
STEP 1 — SPEC-READ
════════════════════════════════════════════════════════════════════════

Run:  git diff HEAD -- {feature_dir}/docs/spec/
Read the diff carefully. If an impl-suggestion was provided, read it now.
Summarise what has changed and what the implementation must achieve before proceeding.

{human_approval_section}
════════════════════════════════════════════════════════════════════════
STEP 3 — LOCK
════════════════════════════════════════════════════════════════════════

Set scope marker and register cleanup trap as your FIRST write action:
  touch {repo_root}/.rabbit-scope-active-{feature_name}
  trap 'rm -f {repo_root}/.rabbit-scope-active-{feature_name}' EXIT

════════════════════════════════════════════════════════════════════════
STEP 4 — TEST-WRITE
════════════════════════════════════════════════════════════════════════

1. Read all existing tests in {feature_dir}/test/
2. Compare each spec behaviour against existing tests.
3. For each behaviour with no e2e test: add one now. (E2E TEST RULE applies.)
4. Commit new/updated tests:
   git add {feature_dir}/test/
   git commit -m "test({feature_name}): add e2e tests for spec behaviours"

════════════════════════════════════════════════════════════════════════
STEP 5 — TEST-RED
════════════════════════════════════════════════════════════════════════

Run: python3 {feature_dir}/test/run.py
Verify tests FAIL. If they already pass (no implementation gap), document why and proceed.
Advance state:
  python3 {tdd_step_py} transition {feature_dir} test-red

════════════════════════════════════════════════════════════════════════
STEP 6 — IMPLEMENT
════════════════════════════════════════════════════════════════════════

Max iterations: {args.max_iterations}

Loop (repeat until green or max iterations reached):
  1. Write/update implementation files for {feature_name}
  2. Run: python3 {feature_dir}/test/run.py
  3. If tests pass: break loop
  4. If iteration == {args.max_iterations}: emit this HANDOFF and stop:
       HANDOFF:
         feature: {feature_name}
         tdd_state: impl
         test_result: fail
         failure_reason: max_iterations_reached
         tdd_report_path: null
         notes: Reached {args.max_iterations} iterations without test-green

On success — advance state:
  python3 {tdd_step_py} transition {feature_dir} impl
  python3 {tdd_step_py} transition {feature_dir} test-green

════════════════════════════════════════════════════════════════════════
STEP 7 — CODE-REVIEW
════════════════════════════════════════════════════════════════════════

Invoke: Skill("superpowers:code-reviewer")
The review covers ALL changed files: tests and functional code.

{code_review_loop_note}

════════════════════════════════════════════════════════════════════════
STEP 8 — TEST-GREEN
════════════════════════════════════════════════════════════════════════

Run final test suite to confirm pass:
  python3 {feature_dir}/test/run.py

Write tdd-report (gitignored — NEVER commit):
  mkdir -p {repo_root}/.rabbit/
  Path: {repo_root}/.rabbit/tdd-report-{feature_name}.json
  {{
    "schema_version": "1.0.0",
    "feature": "{feature_name}",
    "linked_item": "{linked_item_value}",
    "item_type": "{item_type_value}",
    "spec_changes": "<yes|no>",
    "spec_no_change_reason": "<reason or null>",
    "impl_summary": "<one paragraph describing what was implemented>",
    "spec_compliance": "<pass|fail>",
    "spec_compliance_notes": "<unaddressed invariants or null>",
    "test_result": "pass",
    "tdd_state": "test-green",
    "impl_commit": "<git rev-parse HEAD>"
  }}

════════════════════════════════════════════════════════════════════════
STEP 9 — UNLOCK
════════════════════════════════════════════════════════════════════════

Before emitting HANDOFF, commit the tdd_state transition so the dispatcher
does not have to commit feature.json manually:

  git add {feature_dir}/feature.json
  git commit -m "chore({feature_name}): advance tdd_state to test-green"

Scope marker removed automatically by trap on EXIT.

════════════════════════════════════════════════════════════════════════
HANDOFF (emit on completion)
════════════════════════════════════════════════════════════════════════

HANDOFF:
  feature: {feature_name}
  tdd_state: test-green
  test_result: pass
  spec_compliance: <pass|fail>
  tdd_report_path: {repo_root}/.rabbit/tdd-report-{feature_name}.json
  notes: <brief summary>
"""

    sys.stdout.write(prompt)
    sys.stderr.write(f"dispatch-tdd-subagent: prompt ready for feature '{feature_name}'\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
