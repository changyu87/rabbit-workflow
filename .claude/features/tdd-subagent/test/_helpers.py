"""Shared helpers for tdd-subagent tests.

Resolves repo paths and runs dispatch-tdd-subagent.py. Each test imports
from here to avoid path-resolution boilerplate. Not a test file itself
(does not start with `test-`); the runner ignores it.
"""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REPO_ROOT = os.path.abspath(os.path.join(FEATURE_DIR, "..", "..", ".."))
DISPATCH_PY = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")


def _resolve_spec_md(feature_dir):
    """Resolve this feature's spec.md dual-read (issue #399 Phase 2):
    specs/ preferred, legacy docs/spec/ fallback."""
    preferred = os.path.join(feature_dir, "specs", "spec.md")
    if os.path.isfile(preferred):
        return preferred
    return os.path.join(feature_dir, "docs", "spec", "spec.md")


SPEC_PATH = _resolve_spec_md(FEATURE_DIR)
AGENT_PATH = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
CONTRACT_SCRIPTS = os.path.join(REPO_ROOT, ".claude", "features", "contract", "scripts")


def run_dispatch(*args, scope="tdd-subagent", spec=None, check=False):
    """Run dispatch-tdd-subagent.py with --scope and --spec defaulted to
    this feature, plus any additional args. Returns CompletedProcess."""
    if spec is None:
        spec = SPEC_PATH
    cmd = [sys.executable, DISPATCH_PY, "--scope", scope, "--spec", spec] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def run_dispatch_raw(*args, check=False):
    """Run dispatch-tdd-subagent.py with exactly the args provided
    (no defaulted --scope/--spec). Returns CompletedProcess."""
    cmd = [sys.executable, DISPATCH_PY] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def report(passed, failed):
    """Standard PASS/FAIL summary. Exits with non-zero if any failed."""
    total = passed + failed
    if failed == 0:
        print(f"PASS: {passed}/{total}")
        sys.exit(0)
    print(f"FAIL: {failed}/{total}")
    sys.exit(1)
