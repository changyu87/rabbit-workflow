#!/usr/bin/env python3
"""run.py — run all contract feature tests in sequence.

Non-interactive. Exits non-zero on first failure. Per Inv 21, this runner
MUST invoke every active test-*.py file in this directory.
"""

import os
import sys
import subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def run_test(script):
    print(f"=== {script} ===")
    result = subprocess.run(
        ["python3", os.path.join(TEST_DIR, script)]
    )
    if result.returncode != 0:
        print(f"--- FAIL: {script} ---", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"--- PASS: {script} ---")
    print()


run_test("test-files-exist.py")
run_test("test-policy-block.py")
run_test("test-templates-have-version.py")
run_test("test-schemas-valid-json.py")
run_test("test-rabbit-triage.py")
run_test("test-rabbit-triage-centralized.py")
run_test("test-dispatch.py")
run_test("test-validate-no-bugs-root.py")
run_test("test-validate-feature-real-features.py")
run_test("test-audit-orphan-storage.py")
run_test("test-dispatch-spec-update.py")
run_test("test-skill-command-templates.py")
run_test("test-rabbit-print-messages-schema.py")
run_test("test-rabbit-print-renderer.py")
run_test("test-rabbit-print-named-wrappers.py")
run_test("test-rabbit-block-assembler.py")
run_test("test-workspace-map.py")
run_test("test-build-contract.py")
run_test("test-check-naming-bans-rbt.py")
run_test("test-python-only-stack.py")
run_test("test-cli-naming-convention.py")
run_test("test-check-tests-non-interactive.py")
run_test("test-find-feature.py")
run_test("test-validate-feature-runner-python.py")
run_test("test-contract-scripts-have-docstrings.py")
run_test("test-run-invokes-all-active-tests.py")
run_test("test-dead-relink-tests-deleted.py")
run_test("test-feature-schema-permissive.py")
run_test("test-template-schema-producer-live-refs.py")
run_test("test-check-sentinel-scans-py.py")
run_test("test-bug-template-version-field.py")
run_test("test-feature-template-validates-schema.py")
run_test("test-dispatch-feature-edit-path-detect.py")
run_test("test-find-feature-scope-and-handles.py")
run_test("test-audit-orphan-backlogs.py")
run_test("test-check-symlinks-deep.py")
run_test("test-check-no-main-edits-protected-set.py")
run_test("test-check-imports-resolve-surface-dirs.py")
run_test("test-workspace-structure-naming.py")
run_test("test-bug-fixes-cycle.py")
run_test("test-workspace-declares-all-features.py")

print("ALL TESTS PASSED")
