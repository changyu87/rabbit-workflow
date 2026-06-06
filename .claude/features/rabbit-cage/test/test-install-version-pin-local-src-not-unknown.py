#!/usr/bin/env python3
"""test-install-version-pin-local-src-not-unknown.py — e2e regression.

A local `--src` install (no published ref: RABBIT_INSTALLED_REF unset) must
NOT pin the literal string "unknown" into <target>/.version. Pinning "unknown"
makes the SessionStart welcome box read `rabbit vunknown` and the update-check
headline read `current: unknown ... on channel unknown` — comparing a real
release against a sentinel.

Instead, `install.write_version_pin` derives a MEANINGFUL local marker:
  - the source git short SHA (e.g. `local-1a2b3c4`) when --src is a git
    checkout, OR
  - the literal `local` when no SHA is resolvable.

This test pins both the unit contract (write_version_pin output) and the
end-to-end banner consequence: feeding the produced .version through the
deployed session-start dispatcher yields a box that contains NEITHER
`vunknown` NOR `channel unknown`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"
RABBIT_CAGE = REPO / ".claude/features/rabbit-cage"
SESSION_SRC = RABBIT_CAGE / "hooks/session-start-dispatcher.py"
DISPATCHER_LIB_SRC = RABBIT_CAGE / "hooks/_dispatcher_lib.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(path: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(
        ["git", "-C", str(path), *args],
        check=True, capture_output=True, text=True, env=env)


def _clear_ref_env() -> dict:
    saved = {}
    for k in ("RABBIT_INSTALLED_REF",):
        saved[k] = os.environ.pop(k, None)
    return saved


def _restore_env(saved: dict) -> None:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_local_src_git_checkout_pins_short_sha_not_unknown():
    """A git-checkout --src with no RABBIT_INSTALLED_REF pins a meaningful
    local marker carrying the source short SHA — never the literal 'unknown'."""
    mod = _load_install()
    saved = _clear_ref_env()
    try:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            dst = Path(td) / "dst"
            src.mkdir()
            dst.mkdir()
            (src / "f.txt").write_text("x\n")
            _git(src, "init", "-q")
            _git(src, "add", "-A")
            _git(src, "commit", "-q", "-m", "init")
            short_sha = subprocess.check_output(
                ["git", "-C", str(src), "rev-parse", "--short", "HEAD"],
                text=True).strip()

            mod.write_version_pin(dst, src)
            content = (dst / ".version").read_text().strip()

            assert content != "unknown", (
                f".version must not be the literal 'unknown' for a local "
                f"--src install; got {content!r}")
            assert short_sha in content, (
                f".version should carry the source short SHA {short_sha!r}; "
                f"got {content!r}")
    finally:
        _restore_env(saved)
    print("PASS test_local_src_git_checkout_pins_short_sha_not_unknown")


def test_local_src_non_git_pins_local_not_unknown():
    """A non-git --src with no RABBIT_INSTALLED_REF falls back to a meaningful
    literal (`local`) — still never 'unknown'."""
    mod = _load_install()
    saved = _clear_ref_env()
    try:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            dst = Path(td) / "dst"
            src.mkdir()
            dst.mkdir()
            mod.write_version_pin(dst, src)
            content = (dst / ".version").read_text().strip()
            assert content != "unknown", (
                f".version must not be 'unknown' for a non-git local --src; "
                f"got {content!r}")
            assert content, ".version must be non-empty"
    finally:
        _restore_env(saved)
    print("PASS test_local_src_non_git_pins_local_not_unknown")


def test_explicit_ref_env_still_honored():
    """RABBIT_INSTALLED_REF, when set, still wins verbatim (no regression of
    the published-install path)."""
    mod = _load_install()
    saved = {"RABBIT_INSTALLED_REF": os.environ.get("RABBIT_INSTALLED_REF")}
    os.environ["RABBIT_INSTALLED_REF"] = "v9.9.9"
    try:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            dst = Path(td) / "dst"
            src.mkdir()
            dst.mkdir()
            mod.write_version_pin(dst, src)
            content = (dst / ".version").read_text().strip()
            assert content == "v9.9.9", (
                f"explicit RABBIT_INSTALLED_REF must win verbatim; "
                f"got {content!r}")
    finally:
        _restore_env(saved)
    print("PASS test_explicit_ref_env_still_honored")


def _build_install_root(td: Path, version_text: str) -> Path:
    install_root = td / "rabbit_install"
    install_root.mkdir()
    hooks_dir = install_root / ".claude/hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy2(SESSION_SRC, hooks_dir / "session-start-dispatcher.py")
    shutil.copy2(DISPATCHER_LIB_SRC, hooks_dir / "_dispatcher_lib.py")
    (install_root / ".claude/features").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REPO / ".claude/features/contract",
        install_root / ".claude/features/contract")
    shutil.copytree(
        REPO / ".claude/features/rabbit-meta",
        install_root / ".claude/features/rabbit-meta")
    cage_dir = install_root / ".claude/features/rabbit-cage"
    cage_dir.mkdir(parents=True)
    shutil.copy2(RABBIT_CAGE_FEATURE_JSON, cage_dir / "feature.json")
    pol = install_root / ".claude/features/policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("# stub\n")
    (pol / "spec-rules.md").write_text("# stub\n")
    (pol / "coding-rules.md").write_text("# stub\n")
    (install_root / ".version").write_text(version_text + "\n")
    return install_root


def _system_message(stdout: str) -> str:
    stdout = stdout.strip()
    assert stdout, "expected JSON on stdout"
    return json.loads(stdout).get("systemMessage", "")


def test_banner_for_local_src_has_no_vunknown_or_channel_unknown():
    """End-to-end: the .version produced by a local git --src install, fed
    through the deployed SessionStart dispatcher, yields a box that contains
    NEITHER 'vunknown' NOR 'channel unknown'."""
    mod = _load_install()
    saved = _clear_ref_env()
    try:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td).resolve()
            src = td_path / "src"
            holder = td_path / "holder"
            src.mkdir()
            holder.mkdir()
            (src / "f.txt").write_text("x\n")
            _git(src, "init", "-q")
            _git(src, "add", "-A")
            _git(src, "commit", "-q", "-m", "init")

            mod.write_version_pin(holder, src)
            version_text = (holder / ".version").read_text().strip()

            install_root = _build_install_root(td_path, version_text)
            env = {**os.environ, "RABBIT_ROOT": str(install_root)}
            # Throttle the network update-check off so the box renders without
            # a live fetch; the banner-box assertion is what matters here.
            env["RABBIT_RELEASE_CHECK_INTERVAL"] = "999999999"
            dispatcher = install_root / ".claude/hooks/session-start-dispatcher.py"
            proc = subprocess.run(
                [sys.executable, str(dispatcher)],
                input="", capture_output=True, text=True, env=env,
                cwd=str(install_root))
            assert proc.returncode == 0, f"dispatcher failed: {proc.stderr!r}"
            sysmsg = _system_message(proc.stdout)
            assert "vunknown" not in sysmsg, (
                f"banner must not contain 'vunknown'; got {sysmsg!r}")
            assert "channel unknown" not in sysmsg, (
                f"banner must not contain 'channel unknown'; got {sysmsg!r}")
    finally:
        _restore_env(saved)
    print("PASS test_banner_for_local_src_has_no_vunknown_or_channel_unknown")


def main() -> int:
    test_local_src_git_checkout_pins_short_sha_not_unknown()
    test_local_src_non_git_pins_local_not_unknown()
    test_explicit_ref_env_still_honored()
    test_banner_for_local_src_has_no_vunknown_or_channel_unknown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
