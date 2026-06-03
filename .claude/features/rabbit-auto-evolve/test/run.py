#!/usr/bin/env python3
"""run.py — run all rabbit-auto-evolve feature tests in sequence.

Non-interactive. Exits non-zero on first failure. Per contract Inv 17, this
runner MUST invoke every active test-*.py file in this directory.
"""

import os
import sys
import subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def run_test(script):
    print(f"=== {script} ===")
    result = subprocess.run(
        [sys.executable, os.path.join(TEST_DIR, script)]
    )
    if result.returncode != 0:
        print(f"--- FAIL: {script} ---", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"--- PASS: {script} ---")
    print()


run_test("test-set-evolve-mode.py")
run_test("test-fetch-queue.py")
run_test("test-triage-rules.py")
run_test("test-plan-batch.py")
run_test("test-triage-batch.py")
run_test("test-safety-check.py")
run_test("test-merge-prs.py")
run_test("test-cleanup-branches.py")
run_test("test-release-bump.py")
run_test("test-classify-merge-restart.py")
run_test("test-state-persistence.py")
run_test("test-tick-skill.py")
run_test("test-start-stop-skill.py")
run_test("test-on-off-surface.py")
run_test("test-discovered-issues.py")
run_test("test-skill-no-askuserquestion-rule.py")
run_test("test-banner-suppression.py")
run_test("test-feature-shape.py")
run_test("test-loop-markers.py")
run_test("test-check-preconditions.py")
run_test("test-banner-status.py")
run_test("test-markers-gitignored.py")
run_test("test-claude-runtime-files-gitignored.py")
run_test("test-spec-convergence-invariant.py")
run_test("test-dispatch-shape.py")
run_test("test-spec-dispatch-shape-invariant.py")
run_test("test-specs-layout-migrated.py")

print("ALL TESTS PASSED")
