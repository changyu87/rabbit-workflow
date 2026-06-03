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
run_test("test-triage-priority-flow.py")
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
run_test("test-spec-research-shape-invariant.py")
run_test("test-spec-dispatch-worktree-isolation-invariant.py")
run_test("test-docs-layout.py")
run_test("test-status-report.py")
run_test("test-run-post-merge.py")
run_test("test-spec-post-merge-invariant.py")
run_test("test-check-auto-resume.py")
run_test("test-cron-trigger.py")
run_test("test-tick-headless.py")
run_test("test-spec-cron-invariant.py")
run_test("test-detect-scheduler.py")
run_test("test-running-guard.py")
run_test("test-tick-log.py")
run_test("test-schedule-decision.py")
run_test("test-log-tick.py")
run_test("test-spec-tick-log-invariant.py")
run_test("test-sync-tree.py")
run_test("test-spec-worktree-sync-invariant.py")
run_test("test-self-modifying-migration-registry.py")
run_test("test-self-modifying-migration.py")
run_test("test-spec-self-modifying-migration-invariant.py")
run_test("test-run-tick-phases.py")
run_test("test-tick-persist-convergence.py")
run_test("test-spec-scripted-phase-walk-invariant.py")
run_test("test-stop-holds.py")
run_test("test-guard-before-marker.py")
run_test("test-spec-guard-before-marker-invariant.py")
run_test("test-clean-dispatch-leaks.py")
run_test("test-spec-clean-dispatch-leaks-invariant.py")
run_test("test-spec-branch-switch-guard-invariant.py")

print("ALL TESTS PASSED")
