#!/usr/bin/env python3
# run.py — run all contract feature tests in sequence.
#
# Non-interactive. Exits non-zero on first failure.

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
run_test("test-audit-orphan-storage.py")
run_test("test-relink-no-skills.py")
run_test("test-dispatch-spec-update.py")
run_test("test-skill-command-templates.py")
run_test("test-rabbit-print-schema.py")

run_test("test-workspace-map.py")
run_test("test-build-contract.py")
run_test("test-check-naming-no-rbt.py")
run_test("test-python-only-stack.py")
run_test("test-cli-naming-convention.py")
run_test("test-check-tests-non-interactive.py")

print("ALL TESTS PASSED")
