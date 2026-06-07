#!/usr/bin/env python3
"""test-mode-marker-root-consistency.py — e2e (issue #891).

In a REAL plugin install rabbit lives at ``<project>/.rabbit/`` and
``RABBIT_ROOT`` is set to that ``.rabbit`` dir; the ``.claude/features`` tree
lives UNDER ``.rabbit``. The SessionStart dispatcher resolves ``repo_root`` to
``RABBIT_ROOT`` and used to forward it verbatim to
``contract.lib.runtime.write_mode_marker``, which APPENDS ``.rabbit`` to its
``repo_root`` arg — so the marker landed at the DOUBLED path
``<project>/.rabbit/.rabbit/.runtime/mode``. But ``scope-guard.py`` derives its
root from ``git rev-parse --show-toplevel`` (= ``<project>``) and READS the
SINGLE path ``<project>/.rabbit/.runtime/mode``. Write and read disagreed by
one ``.rabbit`` level, so plugin mode was mis-detected.

This suite pins the WRITE path and the scope-guard READ path to the SAME
canonical location ``<project>/.rabbit/.runtime/mode`` in a faithful plugin
layout, and asserts standalone mode still resolves correctly.

RED before the caller-side fix in session-start-dispatcher; GREEN after.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HOOKS = REPO / ".claude/features/rabbit-cage/hooks"
SESSION = HOOKS / "session-start-dispatcher.py"
DISPATCHER_LIB = HOOKS / "_dispatcher_lib.py"
SCOPE_GUARD = HOOKS / "scope-guard.py"
RABBIT_CAGE_FEATURE_JSON = REPO / ".claude/features/rabbit-cage/feature.json"


def _deploy_dispatcher(hooks_dir: Path) -> Path:
    """Copy the SessionStart dispatcher + its sibling helper into the layout's
    deployed hooks dir, mirroring the real install. The dispatcher resolves
    repo_root() in standalone mode from `git rev-parse --show-toplevel` of its
    OWN file location, so it MUST run from inside the test layout."""
    hooks_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DISPATCHER_LIB, hooks_dir / "_dispatcher_lib.py")
    dst = hooks_dir / "session-start-dispatcher.py"
    shutil.copy2(SESSION, dst)
    return dst


def _stage_features(features_dir: Path) -> None:
    """Copy the real contract + rabbit-meta features and rabbit-cage's
    feature.json (so the dispatcher enumerates the actual SessionStart
    declarations) plus a minimal policy source under features_dir."""
    features_dir.mkdir(parents=True)
    shutil.copytree(REPO / ".claude/features/contract", features_dir / "contract")
    shutil.copytree(REPO / ".claude/features/rabbit-meta", features_dir / "rabbit-meta")
    cage = features_dir / "rabbit-cage"
    cage.mkdir(parents=True)
    shutil.copy(RABBIT_CAGE_FEATURE_JSON, cage / "feature.json")
    pol = features_dir / "policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("# stub\n")
    (pol / "spec-rules.md").write_text("# stub\n")
    (pol / "coding-rules.md").write_text("# stub\n")


def _run_session_start(dispatcher: Path, rabbit_root: Path, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "RABBIT_ROOT": str(rabbit_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
    )


def _run_session_start_standalone(dispatcher: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Standalone: RABBIT_ROOT unset so repo_root() falls back to git-toplevel
    of the DEPLOYED dispatcher's own location — so the dispatcher MUST be the
    copy inside the test layout."""
    env = {k: v for k, v in os.environ.items() if k != "RABBIT_ROOT"}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
    )


def _deploy_scope_guard(hooks_dir: Path) -> Path:
    """Copy scope-guard.py into the layout's deployed hooks dir, mirroring the
    real install (`<install>/.claude/hooks/scope-guard.py`). scope-guard's
    REPO_ROOT is derived from `git rev-parse --show-toplevel` of its OWN file
    location (NOT cwd, NOT RABBIT_ROOT), so the read path is determined by
    where the hook physically lives."""
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dst = hooks_dir / "scope-guard.py"
    shutil.copy2(SCOPE_GUARD, dst)
    return dst


def _scope_guard_read_path(deployed_scope_guard: Path) -> Path:
    """Re-derive the EXACT path the DEPLOYED scope-guard.py reads for the mode
    marker by importing it from its install location. It reads
    REPO_ROOT/.rabbit/.runtime/mode (Inv 17), REPO_ROOT = git-toplevel of the
    hook's own location."""
    code = (
        "import importlib.util\n"
        f"spec=importlib.util.spec_from_file_location('sg',{str(deployed_scope_guard)!r})\n"
        "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
        "print(str(m.REPO_ROOT / '.rabbit' / '.runtime' / 'mode'))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"scope-guard import failed: {proc.stderr}"
    return Path(proc.stdout.strip())


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)


def test_plugin_write_path_equals_scope_guard_read_path():
    """Faithful plugin layout: RABBIT_ROOT = <project>/.rabbit, features under
    .rabbit. The mode marker MUST land at the SINGLE-.rabbit canonical path
    <project>/.rabbit/.runtime/mode — exactly where scope-guard reads it — and
    NOT at the doubled <project>/.rabbit/.rabbit/.runtime/mode path."""
    with tempfile.TemporaryDirectory() as td:
        project = Path(td).resolve() / "project"
        project.mkdir()
        _git_init(project)
        # Sibling entry next to .rabbit/ so detect_mode sees the plugin signature.
        (project / "user-src.txt").write_text("a user-project file\n")
        rabbit_root = project / ".rabbit"
        rabbit_root.mkdir()
        _stage_features(rabbit_root / ".claude" / "features")
        # Deploy hooks where the real install puts them: <install>/.claude/hooks.
        deployed_sg = _deploy_scope_guard(rabbit_root / ".claude" / "hooks")
        deployed_disp = _deploy_dispatcher(rabbit_root / ".claude" / "hooks")

        proc = _run_session_start(deployed_disp, rabbit_root, cwd=rabbit_root)
        assert proc.returncode == 0, f"dispatcher failed: {proc.stderr}"

        canonical = project / ".rabbit" / ".runtime" / "mode"
        doubled = project / ".rabbit" / ".rabbit" / ".runtime" / "mode"

        assert canonical.is_file(), (
            f"mode marker not at canonical single-.rabbit path {canonical}; "
            f"doubled-present={doubled.is_file()} stderr={proc.stderr!r}"
        )
        # Dual-accept (Inv 50): write_mode_marker writes detect_mode's value
        # VERBATIM, and rabbit-meta is renaming the vendored-mode value from
        # "plugin" to "vendored". Accept EITHER so this stays green across the
        # detect_mode flip.
        assert canonical.read_text() in ("vendored", "plugin"), (
            f"expected 'vendored' or 'plugin', got {canonical.read_text()!r}"
        )
        assert not doubled.is_file(), (
            f"mode marker wrongly written to DOUBLED path {doubled} "
            f"(write path one .rabbit too deep)"
        )

        read_path = _scope_guard_read_path(deployed_sg).resolve()
        assert read_path == canonical.resolve(), (
            f"write path {canonical} != scope-guard read path {read_path}"
        )
    print("PASS test_plugin_write_path_equals_scope_guard_read_path")


def test_standalone_marker_path_unchanged():
    """Standalone (RABBIT_ROOT unset, features directly under the repo root):
    the marker lands at <root>/.rabbit/.runtime/mode and scope-guard reads the
    same path."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve() / "repo"
        root.mkdir()
        _git_init(root)
        _stage_features(root / ".claude" / "features")
        deployed_sg = _deploy_scope_guard(root / ".claude" / "hooks")
        deployed_disp = _deploy_dispatcher(root / ".claude" / "hooks")

        proc = _run_session_start_standalone(deployed_disp, cwd=root)
        assert proc.returncode == 0, f"dispatcher failed: {proc.stderr}"

        marker = root / ".rabbit" / ".runtime" / "mode"
        assert marker.is_file(), (
            f"standalone mode marker missing at {marker}; stderr={proc.stderr!r}"
        )
        assert marker.read_text() == "standalone", (
            f"expected 'standalone', got {marker.read_text()!r}"
        )
        # No doubled path in standalone either.
        doubled = root / ".rabbit" / ".rabbit" / ".runtime" / "mode"
        assert not doubled.is_file(), f"unexpected doubled marker {doubled}"

        read_path = _scope_guard_read_path(deployed_sg).resolve()
        assert read_path == marker.resolve(), (
            f"standalone write path {marker} != scope-guard read path {read_path}"
        )
    print("PASS test_standalone_marker_path_unchanged")


def main() -> int:
    test_plugin_write_path_equals_scope_guard_read_path()
    test_standalone_marker_path_unchanged()
    return 0


if __name__ == "__main__":
    sys.exit(main())
