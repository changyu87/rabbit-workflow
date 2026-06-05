#!/usr/bin/env python3
"""test-install-no-drift-on-first-run.py — a fresh install is drift-free.

Regression for #851 (RABBIT-CAGE-16 class): install.py used to ship the
COMMITTED deployed surfaces as-is via a file-closure copy, without running the
publish flow at install time. If those committed copies were stale (a source
change landed without a republish before the ref was cut), the fresh install
copied the stale bytes, and the first Stop hook's check_manifest_drift
re-published from source, found a diff, REBUILT, and emitted
"Surface drift detected - rebuilt: ..." — alarming a user who made no edits.

The fix: install.py RUNS THE PUBLISH FLOW for surfaces at install time (after
the closure copy + settings rewrite), so the installed surfaces are CANONICAL
and byte-match what check_manifest_drift would republish at runtime. A fresh
install is therefore drift-free on its first Stop.

These are end-to-end tests: they run the REAL user-facing installer
(install.main(), the same call install.sh makes) into a throwaway sandbox, then
run the REAL runtime.check_manifest_drift against the installed tree and assert
it reports NO drift ({'type': 'ok'}).
"""

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

# The Stop-hook alert template check_manifest_drift substitutes {names} into.
_DRIFT_ALERT = {
    "text": "Surface drift detected - rebuilt: {names}",
    "icon": "x",
    "color": "red",
}


def _load_install():
    spec = importlib.util.spec_from_file_location("install_nodrift", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_src_tree(src_root: Path, install_mod) -> None:
    """Copy every file install.main() reads from the real repo into src_root —
    SAME_PATH_FILES + HOOKS + SKILLS + AGENTS + COMMANDS + FEATURE_INCLUDES —
    a faithful stand-in for the extracted upstream tarball."""
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


def _run_install(install_mod, src: Path, dst: Path) -> int:
    saved = sys.argv
    sys.argv = ["install.py", "--src", str(src), "--target", str(dst)]
    try:
        return install_mod.main()
    finally:
        sys.argv = saved


def _drift_check(dst: Path) -> dict:
    """Import the installed tree's own contract.lib.runtime and run
    check_manifest_drift against the install, exactly as the deployed Stop
    hook does on the user's first prompt.

    The deployed Stop hook fires in plugin mode with RABBIT_ROOT set (the
    install writes env.RABBIT_ROOT into settings.json, Inv 19), so publish_hook
    republishes the PLUGIN command form. Replicate that environment here so the
    check faithfully mirrors the user's first Stop."""
    cdir = str(dst / ".claude/features/contract")
    if cdir not in sys.path:
        sys.path.insert(0, cdir)
    # Drop any cached lib.* from a previous sandbox so we bind to THIS tree.
    for mod_name in [m for m in list(sys.modules) if m == "lib" or m.startswith("lib.")]:
        del sys.modules[mod_name]
    from lib import runtime  # noqa: PLC0415
    prev = os.environ.get("RABBIT_ROOT")
    os.environ["RABBIT_ROOT"] = str(dst.resolve())
    try:
        return runtime.check_manifest_drift(dict(_DRIFT_ALERT), repo_root=str(dst))
    finally:
        if prev is None:
            os.environ.pop("RABBIT_ROOT", None)
        else:
            os.environ["RABBIT_ROOT"] = prev


def _install_into(td: Path):
    install = _load_install()
    src = td / "src"
    src.mkdir()
    _build_src_tree(src, install)
    dst = td / "dst"
    rc = _run_install(install, src, dst)
    assert rc == 0, f"install.main() returned {rc}"
    return install, src, dst


def test_fresh_install_reports_no_drift():
    """After a clean install, the runtime drift check reports no rebuild."""
    with tempfile.TemporaryDirectory() as td:
        _install, _src, dst = _install_into(Path(td).resolve())
        res = _drift_check(dst)
        assert res.get("type") == "ok", (
            "fresh install is NOT drift-free; check_manifest_drift would "
            f"rebuild on first Stop: {res!r}"
        )
    print("PASS test_fresh_install_reports_no_drift")


def test_install_canonicalizes_a_stale_committed_surface():
    """Seed a deliberately-stale committed deployed copy in the SOURCE tree
    (as if a source change had landed without a republish before the ref was
    cut), install it, and assert the install canonicalizes it — the runtime
    drift check still reports NO drift.

    The deployed CLAUDE.md is a generated surface (rabbit-cage manifest
    publish_generated). Corrupting the source's top-level CLAUDE.md simulates a
    committed-but-stale surface that the old closure-copy installer would ship
    verbatim, tripping the first-Stop rebuild.
    """
    with tempfile.TemporaryDirectory() as td:
        install = _load_install()
        src = Path(td).resolve() / "src"
        src.mkdir()
        _build_src_tree(src, install)
        # Make the committed top-level CLAUDE.md stale relative to what the
        # generator would produce from policy + policy-header.json.
        stale = src / "CLAUDE.md"
        stale.write_text("STALE COMMITTED SURFACE — not republished\n")
        dst = Path(td).resolve() / "dst"
        rc = _run_install(install, src, dst)
        assert rc == 0, f"install.main() returned {rc}"

        res = _drift_check(dst)
        assert res.get("type") == "ok", (
            "install did not canonicalize a stale committed surface; the "
            f"runtime drift check would rebuild on first Stop: {res!r}"
        )
        # And the installed CLAUDE.md must no longer carry the stale bytes.
        deployed = (dst / "CLAUDE.md").read_text()
        assert "STALE COMMITTED SURFACE" not in deployed, (
            "installed CLAUDE.md still carries the stale committed bytes"
        )
    print("PASS test_install_canonicalizes_a_stale_committed_surface")


def main() -> int:
    test_fresh_install_reports_no_drift()
    test_install_canonicalizes_a_stale_committed_surface()
    print("ALL PASSED test-install-no-drift-on-first-run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
