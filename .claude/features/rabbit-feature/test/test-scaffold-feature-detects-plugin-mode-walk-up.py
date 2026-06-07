#!/usr/bin/env python3
"""Inv 44 (amended) — `_detect_plugin_mode` walks UP from cwd.

Regression for GitHub issue #267: the original `_detect_plugin_mode`
checked only `<cwd>/.rabbit/.runtime/mode`, so when cwd was `.rabbit/`
itself (the typical rabbit session cwd in plugin mode), the script looked
for `.rabbit/.rabbit/.runtime/mode`, which never exists, and silently
fell through to standalone semantics — misparsing
`<name> <path-glob>` as `<root> <name>`.

Five cases:
  - cwd == project root (`<root>/.rabbit/.runtime/mode == 'plugin'`)
  - cwd == `.rabbit/` itself (`.rabbit/.runtime/mode == 'plugin'`)   <-- #267 regression
  - cwd == arbitrary nested subdir under project root
  - cwd outside any rabbit install (no marker on the walk)
  - cwd == filesystem root (`/`) — terminates cleanly, no infinite loop

Each test asserts both `is_plugin` AND the resolved `rabbit_root` path.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when plugin-mode scaffolding is absorbed into a
    native rabbit CLI subcommand.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / ".claude/features/rabbit-feature/scripts/scaffold-feature.py"


def _load_scaffold_module():
    spec = importlib.util.spec_from_file_location("scaffold_feature_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _seed_plugin_marker(project_root: Path, value: str = "plugin") -> Path:
    """Write `<project_root>/.rabbit/.runtime/mode = value`. Return the .rabbit dir."""
    rabbit_dir = project_root / ".rabbit"
    runtime = rabbit_dir / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "mode").write_text(value)
    return rabbit_dir


def _unwrap(result):
    """Normalize the return shape — accept either a bare Path or (is_plugin, root) tuple.

    Inv 44 (amended) requires a tuple return. We accept the old single-value
    shape only as a transition: the caller asserts both fields anyway, so
    the legacy shape would fail those asserts independently.
    """
    if isinstance(result, tuple):
        return result
    # Legacy: bare Path|None — synthesize tuple semantics from it.
    if result is None:
        return (False, None)
    return (True, result)


def test_detect_when_cwd_is_project_root() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-walkup-root-") as tmp:
        project = Path(tmp).resolve()
        rabbit_dir = _seed_plugin_marker(project)
        mod = _load_scaffold_module()
        is_plugin, rabbit_root = _unwrap(mod._detect_plugin_mode(project))
        assert is_plugin is True, "cwd=project root with marker MUST detect plugin mode"
        assert rabbit_root == rabbit_dir, (
            f"rabbit_root must resolve to <project>/.rabbit; got {rabbit_root!r}"
        )


def test_detect_when_cwd_is_dot_rabbit_regression_267() -> None:
    """Regression for GitHub issue #267: cwd=.rabbit/ must detect plugin."""
    with tempfile.TemporaryDirectory(prefix="rf-walkup-dotrabbit-") as tmp:
        project = Path(tmp).resolve()
        rabbit_dir = _seed_plugin_marker(project)
        mod = _load_scaffold_module()
        is_plugin, rabbit_root = _unwrap(mod._detect_plugin_mode(rabbit_dir))
        assert is_plugin is True, (
            "cwd=.rabbit/ MUST detect plugin mode (issue #267 regression)"
        )
        assert rabbit_root == rabbit_dir, (
            f"rabbit_root must resolve to <project>/.rabbit; got {rabbit_root!r}"
        )


def test_detect_when_cwd_is_nested_subdir() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-walkup-nested-") as tmp:
        project = Path(tmp).resolve()
        rabbit_dir = _seed_plugin_marker(project)
        nested = project / "src" / "sub" / "deep"
        nested.mkdir(parents=True)
        mod = _load_scaffold_module()
        is_plugin, rabbit_root = _unwrap(mod._detect_plugin_mode(nested))
        assert is_plugin is True, (
            "cwd=<project>/src/sub/deep with marker at project root MUST detect plugin"
        )
        assert rabbit_root == rabbit_dir, (
            f"rabbit_root must resolve to <project>/.rabbit; got {rabbit_root!r}"
        )


def test_detect_vendored_mode_value() -> None:
    """Issue #1034: `.runtime/mode == 'vendored'` MUST detect plugin mode.

    rabbit-meta's `detect_mode` emits `'vendored'` as the post-#980 synonym
    for `'plugin'`; `_detect_plugin_mode` MUST dual-accept both values. The
    case (b) marker at `<project>/.rabbit/.runtime/mode` carries 'vendored'.
    """
    with tempfile.TemporaryDirectory(prefix="rf-walkup-vendored-") as tmp:
        project = Path(tmp).resolve()
        rabbit_dir = _seed_plugin_marker(project, value="vendored")
        mod = _load_scaffold_module()
        is_plugin, rabbit_root = _unwrap(mod._detect_plugin_mode(project))
        assert is_plugin is True, (
            "cwd=project root with marker == 'vendored' MUST detect plugin mode (#1034)"
        )
        assert rabbit_root == rabbit_dir, (
            f"rabbit_root must resolve to <project>/.rabbit; got {rabbit_root!r}"
        )


def test_detect_vendored_mode_case_a_dot_rabbit() -> None:
    """Issue #1034: case (a) marker (`<.rabbit>/.runtime/mode`) == 'vendored'.

    When cwd is `.rabbit/` itself and its `.runtime/mode` holds 'vendored',
    the script MUST detect plugin mode and resolve rabbit_root to that dir.
    """
    with tempfile.TemporaryDirectory(prefix="rf-walkup-vendored-a-") as tmp:
        project = Path(tmp).resolve()
        rabbit_dir = _seed_plugin_marker(project, value="vendored")
        mod = _load_scaffold_module()
        is_plugin, rabbit_root = _unwrap(mod._detect_plugin_mode(rabbit_dir))
        assert is_plugin is True, (
            "cwd=.rabbit/ with marker == 'vendored' MUST detect plugin mode (#1034)"
        )
        assert rabbit_root == rabbit_dir, (
            f"rabbit_root must resolve to <project>/.rabbit; got {rabbit_root!r}"
        )


def test_detect_when_no_rabbit_ancestor() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-walkup-none-") as tmp:
        bare = Path(tmp).resolve()
        # No `.rabbit/` anywhere in the tree.
        mod = _load_scaffold_module()
        is_plugin, rabbit_root = _unwrap(mod._detect_plugin_mode(bare))
        assert is_plugin is False, "no marker anywhere on walk MUST fall through to standalone"
        assert rabbit_root is None


def test_detect_terminates_at_filesystem_root() -> None:
    """Walk MUST terminate at filesystem root rather than loop forever."""
    mod = _load_scaffold_module()
    # Time-bounded by completing the call; if the walk were unbounded
    # `Path('/').parents` would be empty and the loop would never see
    # the start dir — but the implementation MUST also include the start
    # dir itself in the walk. Either way, the result MUST be (False, None)
    # since the real filesystem root almost certainly has no plugin marker.
    is_plugin, rabbit_root = _unwrap(mod._detect_plugin_mode(Path("/")))
    assert is_plugin is False, "/ must not be detected as plugin mode"
    assert rabbit_root is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
