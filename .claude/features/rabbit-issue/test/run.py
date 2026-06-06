#!/usr/bin/env python3
"""rabbit-issue test runner.

Registers two flavours of suite:
  - py     — plain python scripts (static checks); pass/fail = exit code
  - pytest — pytest modules (runtime-script e2e tests against gh_shim)
"""
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run_py_suite(script: str) -> bool:
    print(f"=== {script} (py) ===")
    result = subprocess.run([sys.executable, str(SCRIPT_DIR / script)])
    print()
    return result.returncode == 0


def run_pytest_suite(script: str) -> bool:
    print(f"=== {script} (pytest) ===")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(SCRIPT_DIR / script), "-v"]
    )
    print()
    return result.returncode == 0


# (kind, script) pairs. Order matters only for human-readable output.
SUITES = (
    ("py", "test-spec-presence.py"),
    ("py", "test-specs-layout.py"),
    ("py", "test-skill-presence.py"),
    ("py", "test-manifest-shape.py"),
    ("py", "test-owner-sweep.py"),
    ("py", "test-bb-terminology.py"),
    ("py", "test-label-schema-pinned.py"),
    ("py", "test-filed-by-native-exception.py"),
    ("py", "test-script-backed-clean.py"),
    ("pytest", "test-ensure-labels.py"),
    ("pytest", "test-gh-helper-resolves-rabbit-repo.py"),
    ("pytest", "test-link-sub-issue.py"),
    ("pytest", "test-file-item.py"),
    ("pytest", "test-item-status.py"),
    ("pytest", "test-list-items.py"),
    ("pytest", "test-rabbit-managed-guard.py"),
    ("pytest", "test-comments-json-guard.py"),
)

print("rabbit-issue test runner")
print()

total_fail = 0
for kind, script in SUITES:
    runner = run_pytest_suite if kind == "pytest" else run_py_suite
    if not runner(script):
        total_fail += 1

if total_fail == 0:
    print("ALL SUITES PASSED")
    sys.exit(0)
else:
    print(f"FAILED: {total_fail} suite(s) had failures")
    sys.exit(1)
