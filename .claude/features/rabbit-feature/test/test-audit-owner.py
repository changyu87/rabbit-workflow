#!/usr/bin/env python3
"""Inv 50: audit-owner.py team-owner enforcement.

Repo-level features MUST declare feature.json owner == "rabbit-workflow team".
An individual owner FAILS the audit. Covers the standalone script
scripts/audit-owner.py (CLI surface, pass/fail exit codes, failure message
naming the offending feature + its current owner). The script is run directly
(script-tier); the former rabbit-feature-audit skill wrapper was retired once
contract's validate-feature.py exposed single-feature + `all` sweep validation.

Version: 1.1.0
Owner: rabbit-workflow team
Deprecation criterion: when contract.lib.checks.validate_feature is
exposed via a first-class CLI in the contract feature and enforces the
team-owner rule centrally.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "audit-owner.py"

REQUIRED_OWNER = "rabbit-workflow team"


def _run(arg: str):
    return subprocess.run(
        ["python3", str(SCRIPT), arg],
        capture_output=True, text=True,
    )


def _make_feature(tmp: Path, name: str, owner, status: str | None = None) -> Path:
    feat = tmp / name
    feat.mkdir(parents=True)
    data = {"name": name, "owner": owner, "version": "1.0.0"}
    if status is not None:
        data["status"] = status
    (feat / "feature.json").write_text(json.dumps(data))
    return feat


# --- script exists and is executable ----------------------------------------

def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"missing backing script {SCRIPT}"


def test_script_executable() -> None:
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} must be executable"


# --- bad invocation ---------------------------------------------------------

def test_no_args_exit_2() -> None:
    r = subprocess.run(["python3", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2, f"no-arg invocation must exit 2; got {r.returncode}"
    assert "usage" in (r.stderr + r.stdout).lower()


def test_nonexistent_dir_exit_2() -> None:
    r = _run("/no/such/feature/dir/xyz")
    assert r.returncode == 2, f"nonexistent dir must exit 2; got {r.returncode}"


# --- core rule: team owner passes, individual owner fails --------------------

def test_team_owner_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        feat = _make_feature(Path(td), "rabbit-demo", REQUIRED_OWNER)
        r = _run(str(feat))
    assert r.returncode == 0, (
        f"team-owned feature must pass; got exit {r.returncode}\n{r.stderr}"
    )


def test_individual_owner_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        feat = _make_feature(Path(td), "rabbit-demo", "cyxu")
        r = _run(str(feat))
    assert r.returncode == 1, (
        f"individual-owned feature must fail; got exit {r.returncode}\n{r.stdout}"
    )


def test_failure_message_names_feature_and_owner() -> None:
    with tempfile.TemporaryDirectory() as td:
        feat = _make_feature(Path(td), "rabbit-demo", "alice")
        r = _run(str(feat))
    out = r.stdout + r.stderr
    assert "rabbit-demo" in out, f"failure must name the offending feature; got {out!r}"
    assert "alice" in out, f"failure must name the current owner; got {out!r}"
    assert REQUIRED_OWNER in out, (
        f"failure must name the required owner; got {out!r}"
    )


def test_missing_owner_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        feat = Path(td) / "rabbit-demo"
        feat.mkdir()
        (feat / "feature.json").write_text(json.dumps({"name": "rabbit-demo"}))
        r = _run(str(feat))
    assert r.returncode == 1, (
        f"missing owner must fail; got exit {r.returncode}"
    )


def test_object_owner_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        feat = _make_feature(Path(td), "rabbit-demo", {"team": "x"})
        r = _run(str(feat))
    assert r.returncode == 1, (
        f"non-string owner must fail; got exit {r.returncode}"
    )


# --- retired short-circuit (consistent with validate_feature Inv 36b) --------

def test_retired_feature_passes_regardless_of_owner() -> None:
    with tempfile.TemporaryDirectory() as td:
        feat = _make_feature(Path(td), "rabbit-old", "cyxu", status="retired")
        r = _run(str(feat))
    assert r.returncode == 0, (
        f"retired feature must short-circuit to pass; got exit {r.returncode}\n{r.stderr}"
    )


# --- the live tree must pass (acceptance: all features swept to team) --------

def test_all_repo_features_pass() -> None:
    features_root = FEATURE_DIR.parent
    failures = []
    for feat in sorted(features_root.iterdir()):
        if not (feat / "feature.json").is_file():
            continue
        r = _run(str(feat))
        if r.returncode != 0:
            failures.append((feat.name, (r.stdout + r.stderr).strip()))
    assert not failures, f"live tree features failed team-owner audit: {failures}"


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
