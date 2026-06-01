#!/usr/bin/env python3
"""test-install-refuses-without-update.py — e2e: install.py main() refuses
when --target exists and is non-empty UNLESS --update is passed (Inv 22a).

Pins the default-deny behaviour so a future refactor that weakens the
refusal cannot silently overwrite a committed .rabbit/ tree.
"""

import importlib.util
import shutil
import sys
import tempfile
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
    try:
        return install_mod.main()
    finally:
        sys.argv = saved


def test_refuses_when_target_non_empty_and_no_update_flag():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        # First install: clean target, must succeed.
        rc = _run_install(install, ["install.py", "--src", str(src), "--target", str(dst)])
        assert rc == 0, f"first install must succeed; got rc={rc}"

        # Second install WITHOUT --update against the now-populated target:
        # must refuse with nonzero exit code.
        rc2 = _run_install(install, ["install.py", "--src", str(src), "--target", str(dst)])
        assert rc2 != 0, (
            "install.main() without --update must refuse a non-empty target; "
            f"got rc={rc2}"
        )
    print("PASS test_refuses_when_target_non_empty_and_no_update_flag")


def test_accepts_update_flag_on_non_empty_target():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        rc = _run_install(install, ["install.py", "--src", str(src), "--target", str(dst)])
        assert rc == 0

        # With --update, the empty-target check is skipped (Inv 22b).
        rc2 = _run_install(install, ["install.py", "--update", "--src", str(src), "--target", str(dst)])
        assert rc2 == 0, (
            "install.main(--update) must succeed against a non-empty target; "
            f"got rc={rc2}"
        )
    print("PASS test_accepts_update_flag_on_non_empty_target")


def main() -> int:
    test_refuses_when_target_non_empty_and_no_update_flag()
    test_accepts_update_flag_on_non_empty_target()
    return 0


if __name__ == "__main__":
    sys.exit(main())
