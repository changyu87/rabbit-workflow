#!/usr/bin/env python3
"""test-dispatchers.py — integration tests for the three event dispatchers.

Each test invokes the dispatcher hook as a subprocess against an isolated
temp repo populated with synthetic feature.json declarations and asserts
the emitted stdout JSON (or its absence).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HOOKS = REPO / ".claude/features/rabbit-cage/hooks"
STOP = HOOKS / "stop-dispatcher.py"
SESSION = HOOKS / "session-start-dispatcher.py"
UPS = HOOKS / "user-prompt-submit-dispatcher.py"


def _setup_temp_repo(td: Path) -> Path:
    """Build a temp repo containing a real symlink-equivalent to the
    contract feature so the dispatcher imports succeed. Returns the root.
    """
    root = td
    (root / ".claude/features").mkdir(parents=True)
    # Copy the contract feature into the temp repo so the dispatcher's path
    # discovery (walks up from hook file → finds features/contract) works.
    shutil.copytree(
        REPO / ".claude/features/contract",
        root / ".claude/features/contract",
    )
    return root


def _write_feature(root: Path, name: str, payload: dict):
    fdir = root / ".claude/features" / name
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "feature.json").write_text(json.dumps(payload))


def _run_hook(hook_path: Path, repo_root: Path, env_overrides: dict = None):
    env = {**os.environ, "RABBIT_ROOT": str(repo_root)}
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="",
        capture_output=True,
        text=True,
        env=env,
    )
    return proc


def test_stop_dispatcher_emits_print_for_marker():
    with tempfile.TemporaryDirectory() as td:
        root = _setup_temp_repo(Path(td))
        (root / ".some-marker").write_text("on")
        _write_feature(root, "cage", {
            "name": "cage",
            "runtime": {"Stop": [
                {"api": "check_marker_alert",
                 "args": {"path": ".some-marker", "content": None,
                          "alert": {"text": "MARKER-ALERT", "icon": "warn",
                                    "color": "red"}}},
            ]},
        })
        proc = _run_hook(STOP, root)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip(), "expected JSON on stdout"
        out = json.loads(proc.stdout)
        assert "systemMessage" in out
        assert "MARKER-ALERT" in out["systemMessage"]
    print("PASS test_stop_dispatcher_emits_print_for_marker")


def test_stop_dispatcher_silent_when_no_condition():
    with tempfile.TemporaryDirectory() as td:
        root = _setup_temp_repo(Path(td))
        _write_feature(root, "cage", {
            "name": "cage",
            "runtime": {"Stop": [
                {"api": "check_marker_alert",
                 "args": {"path": ".no-marker", "content": None,
                          "alert": {"text": "X", "icon": "i", "color": "red"}}},
            ]},
        })
        proc = _run_hook(STOP, root)
        assert proc.returncode == 0
        assert proc.stdout == "", f"expected empty stdout, got {proc.stdout!r}"
    print("PASS test_stop_dispatcher_silent_when_no_condition")


def test_session_start_dispatcher_welcome_with_policy():
    with tempfile.TemporaryDirectory() as td:
        root = _setup_temp_repo(Path(td))
        # Build a policy directory with a single .md file
        pol = root / ".claude/features/policy"
        pol.mkdir(parents=True)
        (pol / "philosophy.md").write_text("POLICY-CONTENT-MARKER")
        _write_feature(root, "cage", {
            "name": "cage",
            "runtime": {"SessionStart": [
                {"api": "welcome_with_policy",
                 "args": {"policy_source": ".claude/features/policy"}},
            ]},
        })
        proc = _run_hook(SESSION, root)
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        assert "systemMessage" in out
        assert "additionalContext" in out
        assert "POLICY-CONTENT-MARKER" in out["additionalContext"]
    print("PASS test_session_start_dispatcher_welcome_with_policy")


def test_user_prompt_submit_dispatcher_refresh_at_threshold():
    with tempfile.TemporaryDirectory() as td:
        root = _setup_temp_repo(Path(td))
        pol = root / ".claude/features/policy"
        pol.mkdir(parents=True)
        (pol / "x.md").write_text("PRF-CONTENT")
        (root / ".cnt").write_text("0")
        _write_feature(root, "cage", {
            "name": "cage",
            "runtime": {"UserPromptSubmit": [
                {"api": "check_counter_threshold_refresh",
                 "args": {"counter": ".cnt", "env_var": "RABBIT_REFRESH_EVERY",
                          "source": ".claude/features/policy"}},
            ]},
        })
        # Threshold reached
        proc = _run_hook(UPS, root, {"RABBIT_REFRESH_EVERY": "1"})
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        assert out.get("additionalContext", "").startswith("PRF-CONTENT")
        # Below threshold (counter just reset to 0; threshold 100 so next is 1<100)
        proc = _run_hook(UPS, root, {"RABBIT_REFRESH_EVERY": "100"})
        assert proc.returncode == 0
        assert proc.stdout == "", f"expected empty, got {proc.stdout!r}"
    print("PASS test_user_prompt_submit_dispatcher_refresh_at_threshold")


def test_dispatcher_help_flag():
    for h in (STOP, SESSION, UPS):
        proc = subprocess.run(
            [sys.executable, str(h), "--help"],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0
        assert "hook" in proc.stdout.lower(), proc.stdout
    print("PASS test_dispatcher_help_flag")


def main() -> int:
    test_stop_dispatcher_emits_print_for_marker()
    test_stop_dispatcher_silent_when_no_condition()
    test_session_start_dispatcher_welcome_with_policy()
    test_user_prompt_submit_dispatcher_refresh_at_threshold()
    test_dispatcher_help_flag()
    return 0


if __name__ == "__main__":
    sys.exit(main())
