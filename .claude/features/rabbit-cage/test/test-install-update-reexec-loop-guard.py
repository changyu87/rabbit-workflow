#!/usr/bin/env python3
"""test-install-update-reexec-loop-guard.py — e2e: install.py --update with
RABBIT_INSTALL_REEXEC_DONE=1 in env MUST NOT re-exec (Inv 22h
skip-condition (ii), bug #297).

Rationale: the env var is the infinite-loop guard set by the OLD process
just before os.execv. The NEW process (started by the os.execv) inherits
the env, sees the marker, and skips the re-exec branch — one re-exec per
--update invocation is enough.

Approach: monkey-patch os.execv to set a tripwire; pre-set the env var
to '1' before invoking main(); assert tripwire is clean.
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


def test_reexec_loop_guard_skips_reexec():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture = td_path / "fixture"
        fixture.mkdir()
        _build_src_tree(fixture, install)

        # Fresh install so target exists.
        dst = td_path / "dst"
        rc = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
        assert rc == 0

        # Tripwire: monkey-patch install.os.execv.
        tripwire = {"hit": False}

        def fake_execv(executable, argv_list):
            tripwire["hit"] = True
            raise RuntimeError("os.execv must NOT be called when loop-guard env is set")

        original = install.os.execv
        install.os.execv = fake_execv

        # Pre-set the loop-guard env var (this is what the OLD process sets
        # in the real flow before calling os.execv; the NEW process inherits).
        prev = install.os.environ.get("RABBIT_INSTALL_REEXEC_DONE")
        install.os.environ["RABBIT_INSTALL_REEXEC_DONE"] = "1"
        try:
            rc2 = _run_install(
                install,
                ["install.py", "--update", "--src", str(fixture), "--target", str(dst)],
            )
        finally:
            install.os.execv = original
            if prev is None:
                install.os.environ.pop("RABBIT_INSTALL_REEXEC_DONE", None)
            else:
                install.os.environ["RABBIT_INSTALL_REEXEC_DONE"] = prev

        assert rc2 == 0, f"--update with loop-guard set failed: rc={rc2}"
        assert not tripwire["hit"], (
            "os.execv was invoked despite RABBIT_INSTALL_REEXEC_DONE=1; "
            "Inv 22h skip-condition (ii) violated — infinite-loop risk"
        )

    print("PASS test_reexec_loop_guard_skips_reexec")


def main() -> int:
    test_reexec_loop_guard_skips_reexec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
