#!/usr/bin/env python3
"""test-install-closure-sources-exist.py — install closure integrity (#880).

Asserts that EVERY source path declared by install.py's hardcoded file
closure (SAME_PATH_FILES + HOOKS + SKILLS + AGENTS + COMMANDS +
FEATURE_INCLUDES) resolves to a file that EXISTS in the REAL repo.

This is the deterministic guard against a "dangling required-file" abort:
install.main() requires every closure source to exist, so a surface
retirement (e.g. #853 deleting rabbit-feature-audit/SKILL.md) that leaves a
stale entry in install.py silently breaks `curl … install.sh | bash` on
every fresh install (#880). This test catches that class at CI time.

The check itself lives in install.py as the importable function
`check_install_sources_exist(repo_root)` so the cross-feature contract gate
(piece 2 of #880) can wire it to run on ANY feature's surface change — not
only when rabbit-cage is touched. This test exercises that function against
the real repo.

Unlike test-install-e2e-ready-to-run.py before #880, this validates the
closure against the REAL repo surface, NOT against a sandbox copied from the
closure's own list (which can never observe a missing source).
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(subprocess.run(
    ["git", "-C", str(SCRIPT_DIR), "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip())
INSTALL_PY = REPO_ROOT / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_closure_check", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_function_exported():
    mod = _load_install()
    assert hasattr(mod, "check_install_sources_exist"), (
        "install.py must export check_install_sources_exist(repo_root) so the "
        "contract gate can run the closure-integrity check (#880 piece 2)"
    )
    assert callable(mod.check_install_sources_exist)
    print("PASS test_check_function_exported")


def test_all_closure_sources_exist_in_real_repo():
    """Every hardcoded closure source resolves to a file on disk in the repo.

    FAILS (pre-#880-fix) when a SAME_PATH_FILES / SKILLS / FEATURE_INCLUDES
    entry names a source that was retired upstream — the offending path is
    named in the failure message.
    """
    mod = _load_install()
    missing = mod.check_install_sources_exist(REPO_ROOT)
    assert missing == [], (
        "install.py closure references source files absent from the repo "
        "(dangling required-file -> fresh-install abort, #880):\n  "
        + "\n  ".join(missing)
    )
    print("PASS test_all_closure_sources_exist_in_real_repo")


def test_check_detects_a_planted_missing_source():
    """The check is not vacuous: a fabricated closure with a bogus source is
    reported as missing."""
    mod = _load_install()
    bogus = ".claude/features/rabbit-feature/skills/does-not-exist/SKILL.md"
    saved = list(mod.SAME_PATH_FILES)
    try:
        mod.SAME_PATH_FILES = saved + [bogus]
        missing = mod.check_install_sources_exist(REPO_ROOT)
        assert bogus in missing, (
            f"check failed to flag a planted missing source {bogus!r}; "
            f"got {missing}"
        )
    finally:
        mod.SAME_PATH_FILES = saved
    print("PASS test_check_detects_a_planted_missing_source")


def main() -> int:
    test_check_function_exported()
    test_all_closure_sources_exist_in_real_repo()
    test_check_detects_a_planted_missing_source()
    print("ALL PASSED test-install-closure-sources-exist.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
