#!/usr/bin/env python3
"""Issue #921 — rabbit-feature-scaffold is the declared interface for BOTH
single and batch scaffolding.

Background: in plugin-mode decompose, rabbit-decompose shelled out to
`scaffold-feature.py --batch` directly, bypassing the rabbit-feature-scaffold
skill (a layering violation). The fix makes the skill the user-facing primitive
for both modes via a companion `scaffold-batch.py` script (spec-rules.md §4
Script-Backed Orchestration — batch/computed logic lives in a script, not in
model-assembled SKILL.md bash).

These end-to-end tests drive the companion `scaffold-batch.py` as a subprocess
in plugin mode and assert:

  - b1: a JSON file path is accepted and delegates to scaffold-feature.py
        --batch, scaffolding every entry.
  - b2: an inline list of `name [glob...]` entries (separated by `;`) is
        accepted and delegates identically.
  - b3: single mode still works byte-for-byte — a bare `<feature-name>`
        delegates to scaffold-feature.py's existing single-feature surface.
  - b4: SKILL.md documents the batch surface and references the companion
        script (declared skill-level interface, not a raw script shell-out).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature scaffolding is exposed as a native rabbit
    CLI subcommand that owns both single and batch modes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = (
    REPO_ROOT / ".claude/features/rabbit-feature/skills/rabbit-feature-scaffold"
)
BATCH = SKILL_DIR / "scripts/scaffold-batch.py"
SKILL_MD = SKILL_DIR / "SKILL.md"


def _set_plugin_mode(host_root: Path) -> None:
    runtime = host_root / ".rabbit" / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "mode").write_text("plugin")


def _run(args, cwd):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, str(BATCH), *args],
        cwd=str(cwd), env=env, capture_output=True, text=True,
    )


def test_b0_companion_exists_and_executable() -> None:
    assert BATCH.is_file(), f"missing companion script: {BATCH}"
    assert os.access(BATCH, os.X_OK), f"companion must be executable: {BATCH}"


def test_b1_batch_json_file_delegates() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-batch-b1-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        batch = host / "features.json"
        batch.write_text(json.dumps([
            {"name": "alpha-feat", "globs": []},
            {"name": "beta-feat", "globs": []},
        ]))

        res = _run(["--batch", str(batch)], cwd=host)
        assert res.returncode == 0, (
            f"batch JSON file must delegate and succeed; rc={res.returncode}; "
            f"stderr={res.stderr!r}; stdout={res.stdout!r}"
        )
        for name in ("alpha-feat", "beta-feat"):
            d = host / ".rabbit/rabbit-project/features" / name
            assert d.is_dir(), f"missing scaffold dir for {name}: {d}"
            assert (d / "feature.json").is_file()


def test_b2_inline_list_delegates() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-batch-b2-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        (host / "src").mkdir()
        (host / "src" / "a.py").write_text("# a\n")

        # Inline list form: entries separated by ';', each "name [glob ...]".
        res = _run(["--list", "gamma-feat; delta-feat src/**/*.py"], cwd=host)
        assert res.returncode == 0, (
            f"inline list must delegate and succeed; rc={res.returncode}; "
            f"stderr={res.stderr!r}; stdout={res.stdout!r}"
        )
        gd = host / ".rabbit/rabbit-project/features/gamma-feat"
        dd = host / ".rabbit/rabbit-project/features/delta-feat"
        assert gd.is_dir(), f"missing gamma-feat dir: {gd}"
        assert dd.is_dir(), f"missing delta-feat dir: {dd}"
        # delta-feat had a glob, so it must be registered in project-map.json.
        pmap = json.loads(
            (host / ".rabbit/rabbit-project/project-map.json").read_text()
        )
        assert "delta-feat" in (pmap.get("features") or {}), (
            "delta-feat (with glob) must be registered in project-map.json"
        )
        assert (pmap["features"]["delta-feat"]["paths"]) == ["src/**/*.py"]


def test_b3_single_mode_preserved() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-batch-b3-") as tmp:
        host = Path(tmp)
        _set_plugin_mode(host)
        (host / "lib").mkdir()
        (host / "lib" / "x.py").write_text("# x\n")

        # Single mode: a bare <name> [glob...] delegates to the single-feature
        # surface of scaffold-feature.py (existing behaviour preserved).
        res = _run(["solo-feat", "lib/**/*.py"], cwd=host)
        assert res.returncode == 0, (
            f"single mode must be preserved; rc={res.returncode}; "
            f"stderr={res.stderr!r}; stdout={res.stdout!r}"
        )
        d = host / ".rabbit/rabbit-project/features/solo-feat"
        assert d.is_dir(), f"missing single-mode scaffold dir: {d}"
        pmap = json.loads(
            (host / ".rabbit/rabbit-project/project-map.json").read_text()
        )
        assert "solo-feat" in (pmap.get("features") or {})


def test_b4_skill_documents_batch_surface() -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    # The companion script is referenced by relative path from the skill body.
    assert "scripts/scaffold-batch.py" in text, (
        "SKILL.md must reference the companion scaffold-batch.py script as the "
        "declared batch interface (not a raw scaffold-feature.py --batch "
        "shell-out)"
    )
    # The batch surface is documented (a batch input form is named).
    assert "--batch" in text, (
        "SKILL.md must document the --batch invocation surface"
    )
    # Single mode remains documented.
    assert "<feature-name>" in text, (
        "SKILL.md must still document the single-feature form"
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
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
