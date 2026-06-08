#!/usr/bin/env python3
"""Bug #1114 — plugin-mode scaffold must create test/run.py.

`scaffold-feature.py`'s plugin/vendored path (`_scaffold_plugin_feature`)
wrote feature.json, docs/spec.md, and docs/contract.md but never created
`test/run.py`. The standalone path DOES create `test/run.py`. As a result
the feature-touch TDD cycle failed for plugin/vendored-scaffolded features:
`tdd-step.py` could not invoke a non-existent `test/run.py`.

These end-to-end tests drive `scaffold-feature.py` as a subprocess in plugin
mode (both the bare `<name>` greenfield form and the non-empty-glob form)
and assert:

  - p1: non-batch greenfield `<name>` scaffolds `test/run.py` (executable).
  - p2: non-empty-glob `--batch` scaffolds `test/run.py`.
  - p3: the plugin-path `test/run.py` content is IDENTICAL to the standalone
        path's `test/run.py` — the two paths share one runner template, not
        a divergent copy.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when plugin-mode scaffolding is absorbed into a
    native rabbit CLI subcommand.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCAFFOLD = REPO_ROOT / ".claude/features/rabbit-feature/scripts/scaffold-feature.py"


def _set_plugin_mode(host_root: Path) -> None:
    runtime = host_root / ".rabbit" / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "mode").write_text("plugin")


def _run(args, cwd):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), *args],
        cwd=str(cwd), env=env, capture_output=True, text=True,
    )


def _standalone_run_py(tmp_parent: Path) -> str:
    """Scaffold a standalone feature and return its test/run.py content."""
    root = tmp_parent / "standalone-root"
    res = subprocess.run(
        [sys.executable, str(SCAFFOLD), str(root), "ref-feat"],
        env={**os.environ, "RABBIT_ROOT": str(REPO_ROOT)},
        capture_output=True, text=True,
    )
    assert res.returncode == 0, (
        f"standalone scaffold failed; rc={res.returncode}; stderr={res.stderr!r}"
    )
    run_path = root / "ref-feat" / "test" / "run.py"
    assert run_path.is_file(), "standalone scaffold must create test/run.py"
    return run_path.read_text()


def test_p1_nonbatch_greenfield_creates_test_runpy() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-runpy-p1-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)

        res = _run(["greenfield-feat"], cwd=host)
        assert res.returncode == 0, (
            f"plugin greenfield scaffold must succeed; rc={res.returncode}; "
            f"stderr={res.stderr!r}"
        )
        feat_dir = host / ".rabbit/rabbit-project/features/greenfield-feat"
        run_path = feat_dir / "test" / "run.py"
        assert run_path.is_file(), (
            f"plugin-mode scaffold must create test/run.py; missing {run_path}"
        )
        mode = run_path.stat().st_mode
        assert mode & stat.S_IXUSR, "test/run.py must be executable"


def test_p2_nonempty_glob_creates_test_runpy() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-runpy-p2-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        (host / "src").mkdir()
        (host / "src" / "a.py").write_text("# a\n")
        batch = host / "batch.json"
        batch.write_text(json.dumps([{"name": "globbed-feat", "globs": ["src/**/*.py"]}]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode == 0, (
            f"plugin glob scaffold must succeed; rc={res.returncode}; "
            f"stderr={res.stderr!r}"
        )
        run_path = (
            host / ".rabbit/rabbit-project/features/globbed-feat/test/run.py"
        )
        assert run_path.is_file(), (
            f"plugin-mode glob scaffold must create test/run.py; missing {run_path}"
        )


def test_p3_plugin_runpy_matches_standalone() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-runpy-p3-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)

        res = _run(["consistent-feat"], cwd=host)
        assert res.returncode == 0, (
            f"plugin scaffold must succeed; rc={res.returncode}; "
            f"stderr={res.stderr!r}"
        )
        plugin_run = (
            host
            / ".rabbit/rabbit-project/features/consistent-feat/test/run.py"
        ).read_text()

        standalone_run = _standalone_run_py(host)
        assert plugin_run == standalone_run, (
            "plugin and standalone test/run.py must be identical (one shared "
            f"runner template).\nplugin:\n{plugin_run!r}\n"
            f"standalone:\n{standalone_run!r}"
        )


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
    sys.exit(0 if fail == 0 else 1)
