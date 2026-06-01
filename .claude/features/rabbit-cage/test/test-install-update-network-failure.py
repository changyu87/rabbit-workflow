#!/usr/bin/env python3
"""test-install-update-network-failure.py — e2e: when --update self-fetch
fails (e.g. URLError), install.py exits 1 with a clear stderr line and
leaves the target byte-untouched (Inv 22g).
"""

from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
import urllib.error
from contextlib import redirect_stderr
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


def _run_install(install_mod, argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    saved = sys.argv
    sys.argv = argv
    try:
        with redirect_stderr(buf):
            rc = install_mod.main()
    finally:
        sys.argv = saved
    return rc, buf.getvalue()


def _snapshot(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for p in root.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


def test_network_failure_exits_1_and_leaves_target_untouched():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture = td_path / "fixture"
        fixture.mkdir()
        _build_src_tree(fixture, install)
        dst = td_path / "dst"

        # Fresh install so dst has .claude/+.version and runtime closure.
        rc, _ = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
        assert rc == 0

        snapshot_before = _snapshot(dst)

        # Make fetch_upstream raise URLError to simulate network failure.
        def fake_fetch(repo: str, ref: str, dest: Path) -> Path:
            raise urllib.error.URLError("mocked network failure")

        original = getattr(install, "fetch_upstream", None)
        assert original is not None, "install.fetch_upstream is not defined (Inv 22g)"
        install.fetch_upstream = fake_fetch
        try:
            rc2, err = _run_install(install, ["install.py", "--update", "--target", str(dst)])
        finally:
            install.fetch_upstream = original

        assert rc2 == 1, f"network failure must exit 1; got rc={rc2}"
        # Stderr should name the URL / archive path so the operator can diagnose.
        assert "github.com" in err or "archive" in err or "tar.gz" in err, (
            f"stderr must reference the fetch URL; got: {err!r}"
        )
        # Target byte-untouched.
        snapshot_after = _snapshot(dst)
        assert snapshot_after == snapshot_before, (
            "target must be byte-identical after network failure"
        )
    print("PASS test_network_failure_exits_1_and_leaves_target_untouched")


def main() -> int:
    test_network_failure_exits_1_and_leaves_target_untouched()
    return 0


if __name__ == "__main__":
    sys.exit(main())
