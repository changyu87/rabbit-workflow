#!/usr/bin/env python3
"""test-deployed-hooks-execute.py — end-to-end: deployed dispatchers execute.

Copies the source .claude/ tree into a temp target, runs
install.run_publish_loop against the target (the same install path used
in production), then subprocess-invokes every deployed dispatcher hook
with synthetic stdin and asserts (a) no Python traceback in stderr,
(b) the dispatcher exits 0, and (c) stdout is either empty or a single
valid JSON object.

Pins spec invariant: every helper a dispatcher imports at runtime must
be deployed alongside the dispatcher under .claude/hooks/ via rabbit-cage's
MANIFEST. The existing test-dispatchers.py only exercises the source-
location dispatchers where helpers are already adjacent, so a missing
deploy entry slips through it. This test closes that gap.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SOURCE_CLAUDE = REPO / ".claude"
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

DISPATCHER_HOOKS = (
    "stop-dispatcher.py",
    "session-start-dispatcher.py",
    "user-prompt-submit-dispatcher.py",
)


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _deploy_to(target: Path) -> None:
    shutil.copytree(SOURCE_CLAUDE, target / ".claude")
    install = _load_install()
    failures = install.run_publish_loop(str(target))
    assert failures == 0, f"run_publish_loop reported {failures} failure(s)"


def _run_deployed_hook(target: Path, hook_name: str) -> subprocess.CompletedProcess:
    hook = target / ".claude/hooks" / hook_name
    env = {**os.environ, "RABBIT_ROOT": str(target)}
    return subprocess.run(
        [sys.executable, str(hook)],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
    )


def test_deployed_dispatchers_import_helpers_successfully():
    """Each deployed dispatcher must import its helpers without
    ModuleNotFoundError / traceback."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        _deploy_to(target)
        for hook_name in DISPATCHER_HOOKS:
            proc = _run_deployed_hook(target, hook_name)
            assert "Traceback" not in proc.stderr, (
                f"{hook_name} raised at deployed location:\n{proc.stderr}"
            )
            assert "ModuleNotFoundError" not in proc.stderr, (
                f"{hook_name} ModuleNotFoundError at deployed location:\n{proc.stderr}"
            )
            assert proc.returncode == 0, (
                f"{hook_name} exit={proc.returncode}; stderr={proc.stderr!r}"
            )
    print("PASS test_deployed_dispatchers_import_helpers_successfully")


def test_deployed_dispatchers_emit_valid_json_or_empty():
    """Each deployed dispatcher's stdout is empty or a single JSON object."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        _deploy_to(target)
        for hook_name in DISPATCHER_HOOKS:
            proc = _run_deployed_hook(target, hook_name)
            if proc.stdout.strip():
                try:
                    json.loads(proc.stdout)
                except json.JSONDecodeError as e:
                    raise AssertionError(
                        f"{hook_name} non-JSON stdout: {proc.stdout!r}; {e}"
                    )
    print("PASS test_deployed_dispatchers_emit_valid_json_or_empty")


def main() -> int:
    test_deployed_dispatchers_import_helpers_successfully()
    test_deployed_dispatchers_emit_valid_json_or_empty()
    return 0


if __name__ == "__main__":
    sys.exit(main())
