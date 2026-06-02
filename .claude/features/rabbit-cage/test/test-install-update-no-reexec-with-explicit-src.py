#!/usr/bin/env python3
"""test-install-update-no-reexec-with-explicit-src.py — e2e: install.py
--update with explicit --src MUST NOT re-exec (Inv 22h skip-condition (i),
bug #297).

Rationale: when --src is explicit, the source bytes are pinned by the
caller (dev-test path, install.sh first-install path). The in-memory code
and source-of-truth content can be ASSUMED consistent; no version skew.
Re-exec would be unnecessary process churn.

Approach: monkey-patch os.execv inside the install module to set a tripwire
and raise — if the re-exec branch fires, the tripwire is hit and the test
fails. Run install.main(--update --src=<x>) and assert tripwire is clean.
"""

from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_src_tree(src_root: Path, install_mod) -> None:
    def _copy_rel(rel: str) -> None:
        s = REPO / rel
        d = src_root / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    for rel in install_mod.SAME_PATH_FILES:
        _copy_rel(rel)
    for src_rel, _dst_rel in install_mod.HOOKS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.SKILLS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.AGENTS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.COMMANDS:
        _copy_rel(src_rel)
    for feature, paths in install_mod.FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        for rel in paths:
            _copy_rel(f"{base}/{rel}")


def _run_install(install_mod, argv: list[str]) -> int:
    saved = sys.argv
    sys.argv = argv
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = install_mod.main()
    finally:
        sys.argv = saved
    return rc


def test_explicit_src_does_not_reexec():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture = td_path / "fixture"
        fixture.mkdir()
        _build_src_tree(fixture, install)

        # Fresh install so the target exists and is non-empty.
        dst = td_path / "dst"
        rc = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
        assert rc == 0

        # Tripwire: monkey-patch install.os.execv.
        tripwire = {"hit": False}

        def fake_execv(executable, argv_list):
            tripwire["hit"] = True
            raise RuntimeError("os.execv must NOT be called on explicit --src")

        # Patch on the module's `os` reference.
        original = install.os.execv
        install.os.execv = fake_execv
        # Also remove any inherited loop-guard so skip-condition (ii) doesn't
        # short-circuit the test.
        prev_guard = install.os.environ.pop("RABBIT_INSTALL_REEXEC_DONE", None)
        try:
            rc2 = _run_install(
                install,
                ["install.py", "--update", "--src", str(fixture), "--target", str(dst)],
            )
        finally:
            install.os.execv = original
            if prev_guard is not None:
                install.os.environ["RABBIT_INSTALL_REEXEC_DONE"] = prev_guard

        assert rc2 == 0, f"--update --src failed: rc={rc2}"
        assert not tripwire["hit"], (
            "os.execv was invoked under explicit --src; Inv 22h skip-condition (i) violated"
        )

    print("PASS test_explicit_src_does_not_reexec")


def main() -> int:
    test_explicit_src_does_not_reexec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
