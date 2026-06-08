#!/usr/bin/env python3
"""test-runtime-root-resolver.py — e2e (issue #1046).

In a vendored install the session cwd IS the `.rabbit` install dir
(`<host>/.rabbit`) and `RABBIT_ROOT` is set to it. Runtime-artifact writers
that anchor a CWD-RELATIVE literal `.rabbit/` prefix double the segment to
`<host>/.rabbit/.rabbit/...`, so the mode marker (written single-`.rabbit` by
the SessionStart reconciliation) and the doubled artifacts land in DIFFERENT
trees and readers/writers disagree.

This suite pins the CANONICAL runtime-root resolver that rabbit-cage owns
(`lib/runtime_root.rabbit_runtime_root`): given a resolved `repo_root` it
returns the SINGLE `.rabbit/` runtime root regardless of whether `repo_root`
is the vendored `.rabbit` dir (vendored) or the user-project / git toplevel
(standalone). It also asserts rabbit-cage's OWN SessionStart writer routes its
mode-marker reconciliation through the resolver so the marker never doubles.

RED before the resolver exists / before the writer is wired to it; GREEN after.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RABBIT_CAGE = REPO / ".claude/features/rabbit-cage"
RESOLVER_PATH = RABBIT_CAGE / "lib" / "runtime_root.py"
HOOKS = RABBIT_CAGE / "hooks"
SESSION = HOOKS / "session-start-dispatcher.py"
DISPATCHER_LIB = HOOKS / "_dispatcher_lib.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"


def _load_resolver():
    assert RESOLVER_PATH.is_file(), (
        f"canonical runtime-root resolver missing at {RESOLVER_PATH}"
    )
    spec = importlib.util.spec_from_file_location(
        "rabbit_cage_runtime_root", str(RESOLVER_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolver_vendored_does_not_double():
    """Vendored: repo_root IS the `.rabbit` install dir. The runtime root is
    that SAME dir — no extra `.rabbit/` segment is appended."""
    mod = _load_resolver()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        rabbit = host / ".rabbit"
        rabbit.mkdir()
        got = Path(mod.rabbit_runtime_root(str(rabbit)))
        assert got == rabbit, (
            f"vendored: expected runtime root {rabbit} (single .rabbit), "
            f"got {got}"
        )
        # The doubled path is explicitly NOT what the resolver returns.
        doubled = rabbit / ".rabbit"
        assert got != doubled, f"resolver doubled to {doubled}"
    print("PASS test_resolver_vendored_does_not_double")


def test_resolver_standalone_appends_rabbit():
    """Standalone: repo_root is the git toplevel; the runtime root is
    `<repo_root>/.rabbit`."""
    mod = _load_resolver()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve() / "repo"
        root.mkdir()
        got = Path(mod.rabbit_runtime_root(str(root)))
        assert got == root / ".rabbit", (
            f"standalone: expected {root / '.rabbit'}, got {got}"
        )
    print("PASS test_resolver_standalone_appends_rabbit")


def test_resolver_idempotent_under_repeat():
    """Applying the resolver to its own vendored output is stable — a runtime
    root never re-doubles when fed back as repo_root (the doubling failure
    mode the resolver exists to prevent)."""
    mod = _load_resolver()
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve()
        rabbit = host / ".rabbit"
        rabbit.mkdir()
        once = mod.rabbit_runtime_root(str(rabbit))
        twice = mod.rabbit_runtime_root(once)
        assert Path(once) == Path(twice) == rabbit, (
            f"resolver not idempotent on vendored root: {once} -> {twice}"
        )
    print("PASS test_resolver_idempotent_under_repeat")


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)


def _stage_features(features_dir: Path) -> None:
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


def test_sessionstart_writer_uses_resolver_no_double():
    """e2e: a faithful vendored layout (RABBIT_ROOT = <host>/.rabbit, cwd =
    <host>/.rabbit, features under .rabbit). The SessionStart writer MUST land
    the mode marker at the SINGLE-`.rabbit` canonical path via the resolver,
    NOT at the doubled `<host>/.rabbit/.rabbit/.runtime/mode` path."""
    with tempfile.TemporaryDirectory() as td:
        host = Path(td).resolve() / "project"
        host.mkdir()
        _git_init(host)
        (host / "user-src.txt").write_text("a user-project file\n")
        rabbit_root = host / ".rabbit"
        rabbit_root.mkdir()
        _stage_features(rabbit_root / ".claude" / "features")
        hooks_dir = rabbit_root / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        shutil.copy2(DISPATCHER_LIB, hooks_dir / "_dispatcher_lib.py")
        # Ship the resolver into the layout so a deployed dispatcher that
        # imports it resolves the sibling lib at the install location.
        deployed_lib = rabbit_root / ".claude" / "features" / "rabbit-cage" / "lib"
        deployed_lib.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RESOLVER_PATH, deployed_lib / "runtime_root.py")
        init = RABBIT_CAGE / "lib" / "__init__.py"
        if init.is_file():
            shutil.copy2(init, deployed_lib / "__init__.py")
        dispatcher = hooks_dir / "session-start-dispatcher.py"
        shutil.copy2(SESSION, dispatcher)

        env = {**os.environ, "RABBIT_ROOT": str(rabbit_root)}
        proc = subprocess.run(
            [sys.executable, str(dispatcher)],
            input="", capture_output=True, text=True, env=env,
            cwd=str(rabbit_root),
        )
        assert proc.returncode == 0, f"dispatcher failed: {proc.stderr}"

        canonical = host / ".rabbit" / ".runtime" / "mode"
        doubled = host / ".rabbit" / ".rabbit" / ".runtime" / "mode"
        assert canonical.is_file(), (
            f"mode marker not at canonical single-.rabbit path {canonical}; "
            f"doubled-present={doubled.is_file()} stderr={proc.stderr!r}"
        )
        assert not doubled.is_file(), (
            f"mode marker wrongly written to DOUBLED path {doubled}"
        )
        assert canonical.read_text() in ("vendored", "plugin"), (
            f"unexpected marker content {canonical.read_text()!r}"
        )
    print("PASS test_sessionstart_writer_uses_resolver_no_double")


def main() -> int:
    test_resolver_vendored_does_not_double()
    test_resolver_standalone_appends_rabbit()
    test_resolver_idempotent_under_repeat()
    test_sessionstart_writer_uses_resolver_no_double()
    return 0


if __name__ == "__main__":
    sys.exit(main())
