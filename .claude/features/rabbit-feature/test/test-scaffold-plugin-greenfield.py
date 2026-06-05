#!/usr/bin/env python3
"""Bug #902 — plugin-mode scaffold must be symmetric with standalone for
globless (greenfield) features.

Standalone mode lets you scaffold a feature with NO globs (`<root> <name>`
with `[globs...]` optional); plugin mode previously REQUIRED a non-empty
glob list in BOTH the `--batch` form and the non-batch form, so there was
no way to scaffold a greenfield feature in a plugin install. That broke
rabbit-decompose's greenfield scenario.

These end-to-end tests drive `scaffold-feature.py` as a subprocess in plugin
mode and assert:

  - g1: `--batch` entry with EMPTY globs scaffolds the feature dir +
        feature.json (rc 0) and does NOT register a project-map glob entry.
  - g2: plugin non-batch `<name>` with NO globs scaffolds the feature dir +
        feature.json (rc 0), no project-map glob registration.
  - g3: non-empty-glob `--batch` behavior is unchanged (still registers the
        project-map entry, rc 0).
  - g4: genuinely-malformed globs (present but not a list of strings) are
        STILL rejected — only the EMPTY case becomes valid.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when plugin-mode scaffolding is absorbed into a
    native rabbit CLI subcommand.
"""
from __future__ import annotations

import json
import os
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


def test_g1_batch_empty_globs_scaffolds_greenfield() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-greenfield-g1-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        batch = host / "batch.json"
        batch.write_text(json.dumps([{"name": "greenfield-feat", "globs": []}]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode == 0, (
            f"greenfield batch (empty globs) must scaffold; rc={res.returncode}; "
            f"stderr={res.stderr!r}; stdout={res.stdout!r}"
        )
        feat_dir = host / ".rabbit/rabbit-project/features/greenfield-feat"
        assert feat_dir.is_dir(), f"missing scaffold dir: {feat_dir}"
        fj_path = feat_dir / "feature.json"
        assert fj_path.is_file(), "missing feature.json"
        assert (feat_dir / "docs/spec.md").is_file(), "missing docs/spec.md"
        assert (feat_dir / "docs/contract.md").is_file(), "missing docs/contract.md"

        fj = json.loads(fj_path.read_text())
        assert fj.get("name") == "greenfield-feat"
        assert fj.get("paths") == [], (
            f"greenfield feature.json paths must be empty; got {fj.get('paths')!r}"
        )

        # No project-map glob registration for a globless greenfield feature.
        pmap_path = host / ".rabbit/rabbit-project/project-map.json"
        if pmap_path.is_file():
            pmap = json.loads(pmap_path.read_text())
            assert "greenfield-feat" not in (pmap.get("features") or {}), (
                "globless greenfield feature must NOT be registered in "
                f"project-map.json; got {pmap.get('features')!r}"
            )


def test_g2_nonbatch_no_globs_scaffolds_greenfield() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-greenfield-g2-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)

        res = _run(["lonely-feat"], cwd=host)
        assert res.returncode == 0, (
            f"plugin non-batch <name> with no globs must scaffold; "
            f"rc={res.returncode}; stderr={res.stderr!r}; stdout={res.stdout!r}"
        )
        feat_dir = host / ".rabbit/rabbit-project/features/lonely-feat"
        assert feat_dir.is_dir(), f"missing scaffold dir: {feat_dir}"
        fj = json.loads((feat_dir / "feature.json").read_text())
        assert fj.get("name") == "lonely-feat"
        assert fj.get("paths") == [], (
            f"greenfield feature.json paths must be empty; got {fj.get('paths')!r}"
        )
        pmap_path = host / ".rabbit/rabbit-project/project-map.json"
        if pmap_path.is_file():
            pmap = json.loads(pmap_path.read_text())
            assert "lonely-feat" not in (pmap.get("features") or {}), (
                "globless greenfield feature must NOT be registered in project-map.json"
            )


def test_g3_nonempty_globs_unchanged() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-greenfield-g3-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        (host / "src").mkdir()
        (host / "src" / "a.py").write_text("# a\n")
        batch = host / "batch.json"
        batch.write_text(json.dumps([{"name": "globbed-feat", "globs": ["src/**/*.py"]}]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode == 0, (
            f"non-empty-glob batch regressed; rc={res.returncode}; "
            f"stderr={res.stderr!r}"
        )
        pmap_path = host / ".rabbit/rabbit-project/project-map.json"
        assert pmap_path.is_file(), "non-empty-glob feature must register project-map.json"
        pmap = json.loads(pmap_path.read_text())
        entry = (pmap.get("features") or {}).get("globbed-feat")
        assert entry is not None, "globbed-feat must be registered"
        assert entry.get("paths") == ["src/**/*.py"]
        assert entry.get("feature_dir") == "rabbit-project/features/globbed-feat"


def test_g4_malformed_globs_still_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-greenfield-g4-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        batch = host / "batch.json"
        # globs present but not a list of strings (a single string, and a
        # list containing a non-string) — genuinely malformed, must error.
        batch.write_text(json.dumps([{"name": "bad-feat", "globs": "src/**/*.py"}]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode != 0, (
            f"malformed globs (string, not list) must be rejected; rc=0; "
            f"stdout={res.stdout!r}"
        )
        assert not (host / ".rabbit/rabbit-project/features/bad-feat").exists()

        batch.write_text(json.dumps([{"name": "bad-feat2", "globs": [123]}]))
        res2 = _run(["--batch", str(batch)], cwd=host)
        assert res2.returncode != 0, (
            f"malformed globs (list of non-strings) must be rejected; rc=0; "
            f"stdout={res2.stdout!r}"
        )
        assert not (host / ".rabbit/rabbit-project/features/bad-feat2").exists()


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
