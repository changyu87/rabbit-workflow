#!/usr/bin/env python3
"""test-install-update-idempotent.py — e2e: two consecutive `install.main(
--update)` runs against the same source produce zero per-file content
changes on the second pass (Inv 22f).

Both the in-closure file overwrites (content-equality short-circuit via
shutil.copy2 of identical bytes) and the publish_settings merge are
idempotent by construction.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
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
            return install_mod.main()
    finally:
        sys.argv = saved


def _hash_tree(root: Path) -> dict[str, str]:
    """Map relpath -> sha256 for every regular file under root."""
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        out[str(path.relative_to(root))] = h.hexdigest()
    return out


def test_two_consecutive_update_runs_are_byte_identical():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        rc = _run_install(install, ["install.py", "--src", str(src), "--target", str(dst)])
        assert rc == 0

        # First --update: establish the steady-state hashes.
        rc1 = _run_install(install, ["install.py", "--update", "--src", str(src), "--target", str(dst)])
        assert rc1 == 0
        hashes_first = _hash_tree(dst)

        # Second --update against the same source: must produce zero diffs.
        rc2 = _run_install(install, ["install.py", "--update", "--src", str(src), "--target", str(dst)])
        assert rc2 == 0
        hashes_second = _hash_tree(dst)

        # Symmetric-difference reveals any added/removed/changed files.
        changed = []
        all_keys = set(hashes_first) | set(hashes_second)
        for k in sorted(all_keys):
            if hashes_first.get(k) != hashes_second.get(k):
                changed.append(k)
        assert not changed, (
            f"second --update mutated {len(changed)} file(s): {changed[:10]}"
        )
    print("PASS test_two_consecutive_update_runs_are_byte_identical")


def main() -> int:
    test_two_consecutive_update_runs_are_byte_identical()
    return 0


if __name__ == "__main__":
    sys.exit(main())
