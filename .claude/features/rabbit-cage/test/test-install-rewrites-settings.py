#!/usr/bin/env python3
"""test-install-rewrites-settings.py — e2e: install.py main() rewrites
the deployed <target>/.claude/settings.json per Inv 19.

(a) Sets env.RABBIT_ROOT to the absolute path of <target>.
(b) Replaces every literal $(git rev-parse --show-toplevel) substring
    inside any hooks[<event>][].hooks[].command with $RABBIT_ROOT.
(c) Applies the same two edits to the feature-local source copy at
    <target>/.claude/features/rabbit-cage/settings.json (Inv 19c).
(d) All edits are idempotent: re-running yields no further changes.

Strategy: build a minimal src tree containing only the files required by
install.py (top-level CLAUDE.md + .claude/settings.json, the six HOOKS
sources, the SKILLS/AGENTS, and every FEATURE_INCLUDES path) using the
real repository contents. Run install.main() against (src=tmp_src,
target=tmp_dst). Assert the rewrite invariants on the deployed
settings.json. Then re-invoke the rewrite helper and assert no further
changes.
"""

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_src_tree(src_root: Path, install_mod) -> None:
    """Copy every file install.main() needs from the real repo into src_root."""
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


def _walk_command_strings(data: dict):
    """Yield every hooks[<event>][].hooks[].command string in data."""
    hooks = data.get("hooks") or {}
    for _event, entries in hooks.items():
        for entry in entries or []:
            for h in entry.get("hooks") or []:
                cmd = h.get("command")
                if isinstance(cmd, str):
                    yield cmd


def _run_install(install_mod, src: Path, dst: Path) -> int:
    saved = sys.argv
    sys.argv = ["install.py", "--src", str(src), "--target", str(dst)]
    try:
        return install_mod.main()
    finally:
        sys.argv = saved


def test_install_rewrites_env_and_commands():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"
        rc = _run_install(install, src, dst)
        assert rc == 0, f"install.main() returned {rc}"

        settings_path = dst / ".claude/settings.json"
        assert settings_path.is_file(), "deployed settings.json missing"
        data = json.loads(settings_path.read_text())

        # (a) env.RABBIT_ROOT pinned to absolute target path
        assert data.get("env", {}).get("RABBIT_ROOT") == str(dst.resolve()), (
            f"env.RABBIT_ROOT not set correctly: "
            f"{data.get('env', {}).get('RABBIT_ROOT')!r} vs {dst.resolve()!s}"
        )

        # (b) no command string still contains the git rev-parse form
        for cmd in _walk_command_strings(data):
            assert "$(git rev-parse --show-toplevel)" not in cmd, (
                f"command still contains git rev-parse form: {cmd!r}"
            )
            # And the rewritten form is present where it should be (hooks were
            # rewritten — at least one $RABBIT_ROOT reference should remain).
        all_cmds = list(_walk_command_strings(data))
        assert any("$RABBIT_ROOT" in c for c in all_cmds), (
            f"expected at least one $RABBIT_ROOT command after rewrite; got {all_cmds!r}"
        )
        # Suffix preservation: each rewritten command should end with
        # `/.claude/hooks/<name>.py` exactly (literal substring substitution).
        for cmd in all_cmds:
            assert "/.claude/hooks/" in cmd, (
                f"hook command lost its /.claude/hooks/ suffix: {cmd!r}"
            )

        # (c) Inv 19(c): feature-local source copy must also be rewritten,
        # and its content must be identical to the deployed copy so that
        # check_manifest_drift (which republishes from the source) is a no-op.
        source_settings = dst / ".claude/features/rabbit-cage/settings.json"
        assert source_settings.is_file(), (
            "feature-local source settings.json missing from install"
        )
        src_data = json.loads(source_settings.read_text())
        assert src_data.get("env", {}).get("RABBIT_ROOT") == str(dst.resolve()), (
            f"source copy env.RABBIT_ROOT not set correctly: "
            f"{src_data.get('env', {}).get('RABBIT_ROOT')!r} vs {dst.resolve()!s}"
        )
        for cmd in _walk_command_strings(src_data):
            assert "$(git rev-parse --show-toplevel)" not in cmd, (
                f"source copy still contains git rev-parse form: {cmd!r}"
            )
        # Semantic guarantee: republishing settings from the rewritten source
        # against the rewritten deployed copy must be a no-op. Without (c),
        # publish_settings would source-win env.RABBIT_ROOT back to the
        # unrewritten source value, reverting the install on every Stop event.
        deployed_data = json.loads(settings_path.read_text())
        # The keys shared between source and deployed must match exactly,
        # so a source-wins merge does not mutate the deployed copy.
        for key, src_value in src_data.items():
            if key == "hooks":
                continue
            assert deployed_data.get(key) == src_value, (
                f"source[{key!r}]={src_value!r} differs from deployed"
                f"[{key!r}]={deployed_data.get(key)!r}; "
                f"publish_settings source-wins merge would mutate deployed"
            )
    print("PASS test_install_rewrites_env_and_commands")


def test_rewrite_is_idempotent():
    install = _load_install()
    assert hasattr(install, "rewrite_settings_for_plugin"), (
        "install.py must export rewrite_settings_for_plugin(dst_root)"
    )
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"
        rc = _run_install(install, src, dst)
        assert rc == 0

        settings_path = dst / ".claude/settings.json"
        first = settings_path.read_text()
        # Second call: rewrite helper on already-rewritten file is no-op.
        install.rewrite_settings_for_plugin(dst)
        second = settings_path.read_text()
        assert first == second, (
            "rewrite_settings_for_plugin is not idempotent — second run mutated the file"
        )
        # And a third call still matches.
        install.rewrite_settings_for_plugin(dst)
        third = settings_path.read_text()
        assert first == third, "third call mutated the file"
    print("PASS test_rewrite_is_idempotent")


def main() -> int:
    test_install_rewrites_env_and_commands()
    test_rewrite_is_idempotent()
    return 0


if __name__ == "__main__":
    sys.exit(main())
