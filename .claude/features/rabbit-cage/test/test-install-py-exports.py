#!/usr/bin/env python3
"""test-install-py-exports.py — pin both contracts of install.py.

install.py serves two roles simultaneously:

  1. User-facing MVP installer: main() copies an explicit (source, dest)
     closure from an extracted upstream tarball into <project>/.rabbit.
     The closure is declared at module top via SAME_PATH_FILES, HOOKS,
     SKILLS, AGENTS, COMMANDS, FEATURE_INCLUDES.

  2. Dev-test helper: run_publish_loop(target_root) is imported by
     several rabbit-cage test suites (test-deployed-hooks-execute.py,
     test-install-publish-loop.py) to exercise the publish flow against
     a freshly copied .claude tree.

A future rewrite that drops one role silently breaks the other. This
test pins both as a single artifact contract.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_install_py_exists_and_importable():
    assert INSTALL_PY.is_file(), f"install.py missing at {INSTALL_PY}"
    mod = _load_install()
    assert mod is not None
    print("PASS test_install_py_exists_and_importable")


def test_exports_main_callable():
    mod = _load_install()
    assert hasattr(mod, "main"), "install.py must export main()"
    assert callable(mod.main), "install.main must be callable"
    print("PASS test_exports_main_callable")


def test_exports_run_publish_loop_callable():
    mod = _load_install()
    assert hasattr(mod, "run_publish_loop"), (
        "install.py must export run_publish_loop() — imported by "
        "test-deployed-hooks-execute.py + test-install-publish-loop.py"
    )
    assert callable(mod.run_publish_loop), "install.run_publish_loop must be callable"
    print("PASS test_exports_run_publish_loop_callable")


def test_exports_file_closure_constants():
    mod = _load_install()
    for name in ("SAME_PATH_FILES", "HOOKS", "SKILLS", "AGENTS", "COMMANDS", "FEATURE_INCLUDES"):
        assert hasattr(mod, name), f"install.py must export {name} at module top"
    assert isinstance(mod.SAME_PATH_FILES, list)
    assert isinstance(mod.HOOKS, list)
    assert isinstance(mod.SKILLS, list)
    assert isinstance(mod.AGENTS, list)
    assert isinstance(mod.COMMANDS, list)
    assert isinstance(mod.FEATURE_INCLUDES, dict)
    print("PASS test_exports_file_closure_constants")


def test_feature_includes_has_expected_features():
    mod = _load_install()
    expected = {"contract", "policy", "rabbit-cage", "rabbit-meta", "rabbit-feature", "spec-seeder"}
    actual = set(mod.FEATURE_INCLUDES.keys())
    assert actual == expected, (
        f"FEATURE_INCLUDES key drift: expected {sorted(expected)}, got {sorted(actual)}"
    )
    print("PASS test_feature_includes_has_expected_features")


def test_hooks_has_six_entries():
    """HOOKS must lay down 4 rabbit-cage dispatchers + _dispatcher_lib + contract prompt-injector."""
    mod = _load_install()
    assert len(mod.HOOKS) == 6, (
        f"expected 6 HOOKS entries (scope-guard + 3 dispatchers + _dispatcher_lib + prompt-injector); "
        f"got {len(mod.HOOKS)}: {mod.HOOKS}"
    )
    dst_names = {dst for _src, dst in mod.HOOKS}
    required = {
        ".claude/hooks/scope-guard.py",
        ".claude/hooks/session-start-dispatcher.py",
        ".claude/hooks/stop-dispatcher.py",
        ".claude/hooks/user-prompt-submit-dispatcher.py",
        ".claude/hooks/_dispatcher_lib.py",
        ".claude/hooks/prompt-injector.py",
    }
    missing = required - dst_names
    assert not missing, f"HOOKS missing required deploy destinations: {sorted(missing)}"
    print("PASS test_hooks_has_six_entries")


def main() -> int:
    test_install_py_exists_and_importable()
    test_exports_main_callable()
    test_exports_run_publish_loop_callable()
    test_exports_file_closure_constants()
    test_feature_includes_has_expected_features()
    test_hooks_has_six_entries()
    return 0


if __name__ == "__main__":
    sys.exit(main())
