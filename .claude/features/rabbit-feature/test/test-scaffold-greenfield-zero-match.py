#!/usr/bin/env python3
"""Bug #1098 — the zero-match typo guard must not block a GREENFIELD feature
whose declared globs legitimately match ZERO files yet.

`scaffold-feature.py`'s plugin-mode glob path refused to register a feature
when none of its supplied globs matched any existing file ("typo guard").
That is correct for an EXISTING feature (a glob that should match files but
matches none is almost certainly a typo), but WRONG for a brand-new
(greenfield) feature: its globs describe paths that do not exist yet.

The fix honors a `greenfield: true` batch-entry field: a greenfield entry
with zero-match globs is ACCEPTED (scaffolds + registers the declared globs
in project-map.json), while a non-greenfield zero-match entry is STILL
REJECTED (the typo guard survives for the existing-feature case).

End-to-end: each test drives `scaffold-feature.py` as a subprocess in plugin
mode.

  - z1: `greenfield: true` batch entry with zero-match globs scaffolds (rc 0)
        and registers the declared globs in project-map.json.
  - z2: non-greenfield (default) zero-match globs are STILL rejected (rc 1) —
        the typo guard is intact.
  - z3: `greenfield: true` with globs that DO match files behaves like a
        normal registration (rc 0, project-map entry present).

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


def test_z1_greenfield_zero_match_globs_accepted() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-gf-zero-z1-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        batch = host / "batch.json"
        # Globs are supplied but match NOTHING (src/ has no such files yet);
        # greenfield:true marks this a brand-new feature, so it must scaffold.
        batch.write_text(json.dumps([
            {"name": "gf-feat", "globs": ["src/gf/**/*.py"], "greenfield": True}
        ]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode == 0, (
            f"greenfield zero-match globs must scaffold; rc={res.returncode}; "
            f"stderr={res.stderr!r}; stdout={res.stdout!r}"
        )
        feat_dir = host / ".rabbit/rabbit-project/features/gf-feat"
        assert feat_dir.is_dir(), f"missing scaffold dir: {feat_dir}"
        assert (feat_dir / "feature.json").is_file(), "missing feature.json"

        # Declared globs are registered even though they match nothing yet.
        pmap_path = host / ".rabbit/rabbit-project/project-map.json"
        assert pmap_path.is_file(), (
            "greenfield-with-globs feature must register project-map.json"
        )
        pmap = json.loads(pmap_path.read_text())
        entry = (pmap.get("features") or {}).get("gf-feat")
        assert entry is not None, "gf-feat must be registered"
        assert entry.get("paths") == ["src/gf/**/*.py"], (
            f"declared globs must be registered; got {entry.get('paths')!r}"
        )


def test_z2_non_greenfield_zero_match_still_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-gf-zero-z2-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        batch = host / "batch.json"
        # No greenfield flag => default => typo guard must reject zero-match.
        batch.write_text(json.dumps([
            {"name": "typo-feat", "globs": ["src/typo/**/*.py"]}
        ]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode == 1, (
            f"non-greenfield zero-match globs must be rejected (typo guard); "
            f"rc={res.returncode}; stdout={res.stdout!r}"
        )
        assert not (host / ".rabbit/rabbit-project/features/typo-feat").exists()


def test_z3_greenfield_with_matching_globs_registers() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-gf-zero-z3-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        (host / "src").mkdir()
        (host / "src" / "a.py").write_text("# a\n")
        batch = host / "batch.json"
        batch.write_text(json.dumps([
            {"name": "gf-matched", "globs": ["src/**/*.py"], "greenfield": True}
        ]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode == 0, (
            f"greenfield with matching globs must scaffold; rc={res.returncode}; "
            f"stderr={res.stderr!r}"
        )
        pmap_path = host / ".rabbit/rabbit-project/project-map.json"
        assert pmap_path.is_file()
        pmap = json.loads(pmap_path.read_text())
        entry = (pmap.get("features") or {}).get("gf-matched")
        assert entry is not None, "gf-matched must be registered"
        assert entry.get("paths") == ["src/**/*.py"]


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
