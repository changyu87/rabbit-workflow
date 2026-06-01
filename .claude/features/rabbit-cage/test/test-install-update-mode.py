#!/usr/bin/env python3
"""test-install-update-mode.py — e2e: install.main(--update) refreshes in
place (Inv 22).

Asserts the four observable behaviours of update mode:
  (a) Files outside the install closure are preserved byte-identical
      (concretely: <target>/.rabbit/.runtime/ contents).
  (b) Custom user-added entries inside <target>/.claude/settings.json
      (e.g. a permission the user appended) survive the refresh, because
      Inv 22d routes settings.json through publish_settings.
  (c) Files inside the closure are refreshed when the source changes.
  (d) The version pin (<target>/.version) reflects the env-var label
      at refresh time and the dispatcher prints `updating <old> -> <new>`.
"""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_src_tree(src_root: Path, install_mod) -> None:
    def _copy_rel(rel: str) -> None:
        s = REPO / rel
        d = src_root / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    for rel in install_mod.SAME_PATH_FILES:
        _copy_rel(rel)
    for src_rel, _dst_rel in install_mod.HOOKS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.SKILLS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.AGENTS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.COMMANDS:
        _copy_rel(src_rel)
    for feature, paths in install_mod.FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        for rel in paths:
            _copy_rel(f"{base}/{rel}")


def _run_install(install_mod, argv: list[str], env_overrides: dict | None = None) -> tuple[int, str]:
    """Run install.main with argv; capture stdout; restore env on exit."""
    saved_argv = sys.argv
    saved_env = {}
    if env_overrides:
        for k, v in env_overrides.items():
            saved_env[k] = os.environ.get(k)
            os.environ[k] = v
    buf = io.StringIO()
    sys.argv = argv
    try:
        with redirect_stdout(buf):
            rc = install_mod.main()
    finally:
        sys.argv = saved_argv
        if env_overrides:
            for k, prev in saved_env.items():
                if prev is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = prev
    return rc, buf.getvalue()


def test_update_preserves_runtime_tree():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        rc, _ = _run_install(install, ["install.py", "--src", str(src), "--target", str(dst)])
        assert rc == 0

        # Simulate live runtime state outside the closure.
        runtime_dir = dst / ".rabbit/.runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        sentinel = runtime_dir / "sentinel.txt"
        sentinel.write_text("preserve-me")
        sentinel_mtime = sentinel.stat().st_mtime

        rc2, _ = _run_install(
            install, ["install.py", "--update", "--src", str(src), "--target", str(dst)]
        )
        assert rc2 == 0, f"--update rc={rc2}"
        assert sentinel.is_file(), ".rabbit/.runtime/sentinel.txt was deleted by --update"
        assert sentinel.read_text() == "preserve-me", "sentinel content mutated by --update"
        assert sentinel.stat().st_mtime == sentinel_mtime, (
            ".rabbit/.runtime/sentinel.txt was rewritten by --update"
        )
    print("PASS test_update_preserves_runtime_tree")


def test_update_preserves_custom_settings_permission():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        rc, _ = _run_install(install, ["install.py", "--src", str(src), "--target", str(dst)])
        assert rc == 0

        # Add a user-added permission entry to deployed settings.json.
        settings_path = dst / ".claude/settings.json"
        data = json.loads(settings_path.read_text())
        data.setdefault("permissions", {}).setdefault("allow", []).append("Bash(my-tool:*)")
        settings_path.write_text(json.dumps(data, indent=2))

        rc2, _ = _run_install(
            install, ["install.py", "--update", "--src", str(src), "--target", str(dst)]
        )
        assert rc2 == 0

        after = json.loads(settings_path.read_text())
        allow = (after.get("permissions") or {}).get("allow") or []
        assert "Bash(my-tool:*)" in allow, (
            "custom user permission was clobbered by --update "
            f"(allow={allow!r})"
        )
        # Inv 19 plugin-mode rewrites still in effect after merge.
        assert after.get("env", {}).get("RABBIT_ROOT") == str(dst.resolve()), (
            "env.RABBIT_ROOT not rewritten after publish_settings merge"
        )
    print("PASS test_update_preserves_custom_settings_permission")


def test_update_refreshes_closure_file_when_source_changes():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        rc, _ = _run_install(install, ["install.py", "--src", str(src), "--target", str(dst)])
        assert rc == 0

        # Mutate a closure source file and re-run with --update.
        # Pick CLAUDE.md (always in SAME_PATH_FILES).
        target_rel = "CLAUDE.md"
        src_file = src / target_rel
        dst_file = dst / target_rel
        original = dst_file.read_text()
        new_content = original + "\n# update-mode probe\n"
        src_file.write_text(new_content)

        rc2, _ = _run_install(
            install, ["install.py", "--update", "--src", str(src), "--target", str(dst)]
        )
        assert rc2 == 0

        assert dst_file.read_text() == new_content, (
            "closure file CLAUDE.md was not refreshed under --update"
        )
    print("PASS test_update_refreshes_closure_file_when_source_changes")


def test_update_prints_version_transition_and_updates_pin():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        # First install pins version to "old-pin".
        rc, _ = _run_install(
            install,
            ["install.py", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "old-pin"},
        )
        assert rc == 0
        version_file = dst / ".version"
        assert version_file.is_file()
        assert version_file.read_text().strip() == "old-pin"

        # Second install with --update bumps to "new-pin"; prints transition.
        rc2, stdout = _run_install(
            install,
            ["install.py", "--update", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "new-pin"},
        )
        assert rc2 == 0
        assert version_file.read_text().strip() == "new-pin", (
            "version pin not updated by --update"
        )
        # Inv 22e: "updating <old> -> <new>" line emitted.
        assert "updating old-pin -> new-pin" in stdout, (
            f"expected 'updating old-pin -> new-pin' in stdout; got: {stdout!r}"
        )
    print("PASS test_update_prints_version_transition_and_updates_pin")


def main() -> int:
    test_update_preserves_runtime_tree()
    test_update_preserves_custom_settings_permission()
    test_update_refreshes_closure_file_when_source_changes()
    test_update_prints_version_transition_and_updates_pin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
