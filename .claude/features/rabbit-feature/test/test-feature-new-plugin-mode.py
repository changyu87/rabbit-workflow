#!/usr/bin/env python3
"""Task 3.2 — scaffold-feature.py plugin-mode behavior.

Exercises the plugin-mode branch of `scaffold-feature.py`:

  - t1: happy path — `<name> <path-glob>` produces
        `<repo>/.rabbit/rabbit-project/features/<name>/` plus a
        `project-map.json` entry mapping the matched paths.
  - t2: a path-glob that resolves outside the user-project root is rejected
        (path traversal guard).
  - t3: a path-glob whose match is already declared by another feature in
        an existing `project-map.json` is rejected, and the error names the
        conflicting feature.
  - t4: a path-glob that matches no files on disk is rejected (typo guard).
  - t5: standalone-mode invocation (`<root> <name>`) still works unchanged.

The plugin/standalone switch is detected via
`<repo>/.rabbit/.runtime/mode` containing "plugin".

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when plugin-mode scaffolding is absorbed into a
    native rabbit CLI subcommand.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
NEW_FEATURE = REPO_ROOT / ".claude/features/rabbit-feature/scripts/scaffold-feature.py"


def _set_plugin_mode(host_root: Path) -> None:
    """Write the `.rabbit/.runtime/mode` marker that flips plugin mode on."""
    runtime = host_root / ".rabbit" / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "mode").write_text("plugin")


def _run(args, cwd, env_extra=None):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = str(REPO_ROOT)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(NEW_FEATURE), *args],
        cwd=str(cwd), env=env, capture_output=True, text=True,
    )


def test_t1_plugin_happy_path() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-plugin-t1-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        # User-project source files that the glob should match.
        (host / "src").mkdir()
        (host / "src" / "a.py").write_text("# a\n")
        (host / "src" / "b.py").write_text("# b\n")

        res = _run(["my-feature", "src/**/*.py"], cwd=host)
        assert res.returncode == 0, (
            f"plugin-mode happy path failed: rc={res.returncode}; "
            f"stderr={res.stderr!r}; stdout={res.stdout!r}"
        )
        feat_dir = host / ".rabbit/rabbit-project/features/my-feature"
        assert feat_dir.is_dir(), f"missing scaffold dir: {feat_dir}"
        assert (feat_dir / "feature.json").is_file(), "missing feature.json"
        assert (feat_dir / "specs/spec.md").is_file(), "missing specs/spec.md"
        assert (feat_dir / "specs/contract.md").is_file(), "missing specs/contract.md"
        # issue #399: plugin-mode scaffolds also use the specs/ layout.
        assert not (feat_dir / "docs/spec").exists(), (
            "plugin-mode scaffold must NOT create the legacy docs/spec/ layout (issue #399)"
        )

        fj = json.loads((feat_dir / "feature.json").read_text())
        assert fj.get("name") == "my-feature"
        assert fj.get("version") == "0.1.0"
        assert fj.get("paths") == ["src/**/*.py"], (
            f"feature.json paths globs must be the declared list; got {fj.get('paths')!r}"
        )
        assert "owner" in fj and fj["owner"]
        assert "created" in fj and fj["created"]
        assert "deprecation_criterion" in fj
        assert fj["deprecation_criterion"] is None

        pmap_path = host / ".rabbit/rabbit-project/project-map.json"
        assert pmap_path.is_file(), f"missing project-map.json: {pmap_path}"
        pmap = json.loads(pmap_path.read_text())
        assert "schema_version" in pmap, "project-map.json missing schema_version"
        feats = pmap.get("features") or {}
        assert "my-feature" in feats, (
            f"project-map.json must register 'my-feature'; got features={list(feats)}"
        )
        entry = feats["my-feature"]
        assert entry.get("paths") == ["src/**/*.py"]
        assert entry.get("feature_dir") == "rabbit-project/features/my-feature"

        # Plugin-mode MUST print the spec-seeder dispatch instruction so the
        # caller can hand off to the seeder subagent. The output should name
        # both the seeder script and the new feature name.
        out = res.stdout
        assert "dispatch-spec-create.py" in out, (
            f"plugin-mode output must reference dispatch-spec-create.py; got {out!r}"
        )
        assert "my-feature" in out, (
            f"plugin-mode output must name the new feature; got {out!r}"
        )


def test_t2_glob_outside_boundary_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-plugin-t2-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        # Glob that escapes the user-project root.
        res = _run(["escapee", "../../etc/**"], cwd=host)
        assert res.returncode != 0, (
            f"plugin-mode must reject globs outside the user-project root; "
            f"got rc=0; stdout={res.stdout!r}"
        )
        msg = (res.stderr + res.stdout).lower()
        assert "outside" in msg or "traversal" in msg or "boundary" in msg, (
            f"rejection message must explain path-traversal guard; got {res.stderr!r}"
        )
        # And no scaffold should have been created.
        assert not (host / ".rabbit/rabbit-project/features/escapee").exists()


def test_t3_overlap_with_existing_feature_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-plugin-t3-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        (host / "src").mkdir()
        (host / "src" / "a.py").write_text("# a\n")

        # Pre-existing project-map: another feature already owns src/**/*.py.
        pmap_dir = host / ".rabbit/rabbit-project"
        pmap_dir.mkdir(parents=True, exist_ok=True)
        existing = {
            "schema_version": "1.0.0",
            "features": {
                "incumbent": {
                    "paths": ["src/**/*.py"],
                    "feature_dir": "rabbit-project/features/incumbent",
                }
            },
        }
        (pmap_dir / "project-map.json").write_text(json.dumps(existing))

        res = _run(["latecomer", "src/**/*.py"], cwd=host)
        assert res.returncode != 0, (
            f"plugin-mode must reject overlap with existing feature; rc=0; "
            f"stdout={res.stdout!r}"
        )
        msg = res.stderr + res.stdout
        assert "incumbent" in msg, (
            f"overlap error must name the conflicting feature 'incumbent'; got {msg!r}"
        )
        # Scaffold dir must not have been created.
        assert not (host / ".rabbit/rabbit-project/features/latecomer").exists()
        # Existing project-map must be untouched.
        after = json.loads((pmap_dir / "project-map.json").read_text())
        assert after == existing, "project-map.json must be untouched on overlap"


def test_t4_empty_match_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-plugin-t4-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        # No files match this glob.
        res = _run(["ghost-feature", "nonexistent/**/*.py"], cwd=host)
        assert res.returncode != 0, (
            f"plugin-mode must reject globs that match no files; rc=0; "
            f"stdout={res.stdout!r}"
        )
        msg = (res.stderr + res.stdout).lower()
        assert "no" in msg and ("match" in msg or "matches" in msg), (
            f"empty-match error must explain zero matches; got {res.stderr!r}"
        )
        assert not (host / ".rabbit/rabbit-project/features/ghost-feature").exists()


def test_t5_standalone_unchanged() -> None:
    """The existing standalone invocation must continue to work even when
    no plugin-mode marker is present."""
    with tempfile.TemporaryDirectory(prefix="rf-plugin-t5-") as tmp:
        # No `.rabbit/.runtime/mode` -> standalone semantics.
        res = subprocess.run(
            [sys.executable, str(NEW_FEATURE), tmp, "demo-standalone",
             "--owner", "scaffolder-test", "--description", "demo"],
            env={**os.environ, "RABBIT_ROOT": str(REPO_ROOT)},
            capture_output=True, text=True,
        )
        assert res.returncode == 0, (
            f"standalone path regressed: rc={res.returncode}; stderr={res.stderr!r}"
        )
        feat_dir = Path(tmp) / "demo-standalone"
        assert (feat_dir / "feature.json").is_file()
        assert (feat_dir / "specs/spec.md").is_file()
        assert (feat_dir / "specs/contract.md").is_file()
        assert not (feat_dir / "docs/spec").exists(), (
            "standalone scaffold must NOT create the legacy docs/spec/ layout (issue #399)"
        )
        assert (feat_dir / "test/run.py").is_file()
        # Standalone scaffold MUST NOT use the plugin schema (no top-level paths key).
        data = json.loads((feat_dir / "feature.json").read_text())
        assert "paths" not in data, (
            "standalone scaffold must not contain plugin-only 'paths' key"
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
