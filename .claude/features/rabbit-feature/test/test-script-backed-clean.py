#!/usr/bin/env python3
"""Issue #873: rabbit-feature carries zero non-script-backed orchestration
findings.

E2E gate: runs rabbit-housekeep's `check-script-backed.py scan` against the
whole rabbit-feature feature dir and asserts `{"count": 0}`. Every fenced bash
block in the feature's SKILL bodies is either (a) a real script-backed
orchestration step, or (b) an illustrative usage/synopsis snippet explicitly
annotated with the `<!-- example -->` exemption marker shipped in #869.

Also locks the one genuine prompt-tier step that was converted rather than
exempted: Step 2 branch creation in rabbit-feature-touch now invokes the
companion feature-touch.py `create-branch` subcommand (the script owns the
deterministic `feat/<feature-name>-<keywords>` branch-name assembly), so the
SKILL body no longer carries a model-assembled `git checkout -b <branch-name>`.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when script-backed-orchestration linting is provided
natively by the rabbit CLI as a housekeeping subcommand.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FEATURE_DIR = REPO_ROOT / ".claude/features/rabbit-feature"
SCANNER = (
    REPO_ROOT
    / ".claude/features/rabbit-housekeep/scripts/check-script-backed.py"
)
TOUCH_SKILL = FEATURE_DIR / "skills/rabbit-feature-touch/SKILL.md"
COMPANION = (
    FEATURE_DIR / "skills/rabbit-feature-touch/scripts/feature-touch.py"
)


def test_scan_reports_zero_findings() -> None:
    """E2E: the scanner reports no non-script-backed orchestration findings."""
    r = subprocess.run(
        [sys.executable, str(SCANNER), "scan", str(FEATURE_DIR)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"scanner failed: {r.stderr}"
    payload = json.loads(r.stdout)
    assert payload["count"] == 0, (
        "rabbit-feature must carry zero non-script-backed orchestration "
        f"findings; got {payload['count']}:\n"
        + json.dumps(payload["findings"], indent=2)
    )


def test_touch_step2_invokes_companion_create_branch() -> None:
    """Step 2 branch creation is script-backed (converted, not exempted)."""
    body = TOUCH_SKILL.read_text(encoding="utf-8")
    assert "create-branch" in body, (
        "rabbit-feature-touch Step 2 must invoke the companion "
        "feature-touch.py 'create-branch' subcommand rather than a "
        "model-assembled `git checkout -b <branch-name>` step (#873)"
    )
    assert "git checkout -b <branch-name>" not in body, (
        "the model-assembled `git checkout -b <branch-name>` step must be "
        "gone — branch-name assembly belongs in the companion script (#873)"
    )


def test_companion_create_branch_assembles_branch_name() -> None:
    """E2E: create-branch assembles feat/<feature>-<keywords> and checks it
    out in a temp git repo."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "t@t"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "t"], check=True
        )
        (root / "f").write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True
        )
        r = subprocess.run(
            [
                sys.executable,
                str(COMPANION),
                "create-branch",
                "rabbit-feature",
                "Add Some New Thing",
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr
        branch = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert branch == "feat/rabbit-feature-add-some-new-thing", (
            f"unexpected branch name: {branch!r}"
        )

        # Multi-feature form: explicit --multi marker in the branch.
        r2 = subprocess.run(
            [
                sys.executable,
                str(COMPANION),
                "create-branch",
                "--multi",
                "rabbit-feature",
                "tweak two features",
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert r2.returncode == 0, r2.stderr
        branch2 = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert branch2 == "feat/rabbit-feature-multi-tweak-two-features", (
            f"unexpected multi branch name: {branch2!r}"
        )


def test_companion_create_branch_is_executable() -> None:
    assert COMPANION.exists(), f"missing companion: {COMPANION}"
    assert os.access(COMPANION, os.X_OK), (
        f"companion must be executable: {COMPANION}"
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
