#!/usr/bin/env python3
"""test-install-e2e-ready-to-run.py — end-to-end plugin-install verification.

Runs the REAL user-facing installer (install.main(), the same call install.sh
makes after extracting the upstream tarball) into a throwaway sandbox sourced
from the clean repo tree, then asserts the install is structurally complete AND
wired — i.e. "ready to run short of launching Claude". No Claude launch: this
is static readiness verification only. Self-cleaning (tempdir discarded).

The checks (issue #849):

  1. Top-level closure: <target>/CLAUDE.md, README.md, install.py present.
  2. <target>/.claude/settings.json present, and EVERY hook command path it
     declares (PreToolUse / Stop / SessionStart / UserPromptSubmit) resolves to
     a file that EXISTS and is EXECUTABLE in the install — the "it will
     actually fire" check. The install rewrites $(git rev-parse --show-toplevel)
     to $RABBIT_ROOT (== target abspath, Inv 19), so resolution substitutes
     that.
  3. Every shipped feature dir has a valid feature.json (parses, dict,
     non-empty name).
  4. Deployed agent/skill/command/hook copies byte-match their source in the
     install (the deployed-copies-match invariant) — settings-bearing files
     excepted because the installer rewrites them in place (Inv 19).
  5. The rabbit-project command scaffold is deployed
     (<target>/.claude/commands/rabbit-project.md).
  6. No dangling references: settings.json hook commands + every install
     manifest destination point only at files that exist in the install.

This complements the narrower install tests (settings-rewrite, deployed-hooks-
execute via run_publish_loop) by exercising the REAL main() closure end to end
and proving the wired-ness of the whole tree in one pass.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

# Files the installer rewrites in place (Inv 19) — their deployed bytes diverge
# from source by design, so they are excluded from the byte-match check.
_REWRITTEN_BASENAMES = {"settings.json"}


def _load_install():
    spec = importlib.util.spec_from_file_location("install_e2e_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_src_tree(src_root: Path, install_mod) -> None:
    """Copy every file install.main() needs from the real repo into src_root.

    Mirrors the closure main() reads: SAME_PATH_FILES + HOOKS + SKILLS +
    AGENTS + COMMANDS + FEATURE_INCLUDES. Sourcing only these from the clean
    repo tree keeps the sandbox a faithful stand-in for the extracted tarball.
    """
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


def _run_install(install_mod, src: Path, dst: Path) -> int:
    """Invoke the REAL user-facing entry point with its real CLI flags."""
    saved = sys.argv
    sys.argv = ["install.py", "--src", str(src), "--target", str(dst)]
    try:
        return install_mod.main()
    finally:
        sys.argv = saved


def _hook_command_strings(settings: dict):
    """Yield (event, command) for every hooks[event][].hooks[].command."""
    hooks = settings.get("hooks") or {}
    for event, entries in hooks.items():
        for entry in entries or []:
            for h in entry.get("hooks") or []:
                cmd = h.get("command")
                if isinstance(cmd, str):
                    yield event, cmd


def _resolve_hook_path(cmd: str, target: Path) -> Path:
    """Resolve a rewritten hook command string to its on-disk path.

    Post-install the command is `$RABBIT_ROOT/.claude/hooks/<name>.py`, where
    $RABBIT_ROOT == the absolute target path (Inv 19). Substitute it and strip
    any trailing argv tokens (split on whitespace, take the first token).
    """
    token = cmd.split()[0] if cmd.split() else cmd
    token = token.replace("$RABBIT_ROOT", str(target.resolve()))
    return Path(token)


def _install_into(td: Path):
    """Build a sandbox src tree, run the real installer into td/dst, return dst."""
    install = _load_install()
    src = td / "src"
    src.mkdir()
    _build_src_tree(src, install)
    dst = td / "dst"
    rc = _run_install(install, src, dst)
    assert rc == 0, f"install.main() returned {rc}"
    return install, dst


# ───────────────────────────────────────────────────────────────────────────
# Checks
# ───────────────────────────────────────────────────────────────────────────

def test_toplevel_closure_present():
    """Top-level CLAUDE.md / README.md / install.py land in the install."""
    with tempfile.TemporaryDirectory() as td:
        _install, dst = _install_into(Path(td).resolve())
        for name in ("CLAUDE.md", "README.md", "install.py"):
            assert (dst / name).is_file(), f"top-level {name} missing from install"
    print("PASS test_toplevel_closure_present")


def test_every_hook_path_exists_and_executable():
    """settings.json present; every declared hook command resolves to an
    EXISTING, EXECUTABLE file (the 'it will actually fire' check), covering all
    four events the install wires."""
    expected_events = {"PreToolUse", "Stop", "SessionStart", "UserPromptSubmit"}
    with tempfile.TemporaryDirectory() as td:
        _install, dst = _install_into(Path(td).resolve())
        settings_path = dst / ".claude/settings.json"
        assert settings_path.is_file(), "deployed .claude/settings.json missing"
        settings = json.loads(settings_path.read_text())

        seen_events = set()
        n_cmds = 0
        for event, cmd in _hook_command_strings(settings):
            seen_events.add(event)
            n_cmds += 1
            hook_path = _resolve_hook_path(cmd, dst)
            assert hook_path.is_file(), (
                f"{event} hook command resolves to missing file: "
                f"{cmd!r} -> {hook_path}"
            )
            assert os.access(hook_path, os.X_OK), (
                f"{event} hook file is not executable (won't fire): {hook_path}"
            )
        assert n_cmds > 0, "settings.json declares no hook commands"
        assert expected_events <= seen_events, (
            f"settings.json missing wired events: "
            f"{sorted(expected_events - seen_events)}"
        )
    print("PASS test_every_hook_path_exists_and_executable")


def test_every_feature_dir_has_valid_feature_json():
    """Every shipped feature dir carries a parseable, named feature.json."""
    with tempfile.TemporaryDirectory() as td:
        _install, dst = _install_into(Path(td).resolve())
        features_root = dst / ".claude/features"
        assert features_root.is_dir(), "no .claude/features in install"
        feature_dirs = [p for p in features_root.iterdir() if p.is_dir()]
        assert feature_dirs, "install shipped zero feature dirs"
        for fdir in feature_dirs:
            fj = fdir / "feature.json"
            assert fj.is_file(), f"{fdir.name}: feature.json missing"
            data = json.loads(fj.read_text())
            assert isinstance(data, dict), f"{fdir.name}: feature.json not an object"
            assert str(data.get("name", "")).strip(), (
                f"{fdir.name}: feature.json has empty/absent name"
            )
    print("PASS test_every_feature_dir_has_valid_feature_json")


def test_deployed_copies_match_source():
    """Deployed agent/skill/command/hook copies byte-match their feature-local
    source within the install (the deployed-copies-match invariant). Files the
    installer rewrites in place (settings.json) are excepted."""
    with tempfile.TemporaryDirectory() as td:
        install, dst = _install_into(Path(td).resolve())

        deployed_pairs = (
            list(install.HOOKS)
            + list(install.SKILLS)
            + list(install.AGENTS)
            + list(install.COMMANDS)
        )
        checked = 0
        for src_rel, dst_rel in deployed_pairs:
            if Path(dst_rel).name in _REWRITTEN_BASENAMES:
                continue
            src_file = dst / src_rel
            dst_file = dst / dst_rel
            assert src_file.is_file(), f"feature-local source missing: {src_rel}"
            assert dst_file.is_file(), f"deployed copy missing: {dst_rel}"
            assert src_file.read_bytes() == dst_file.read_bytes(), (
                f"deployed copy diverges from source: {dst_rel} != {src_rel}"
            )
            checked += 1
        assert checked > 0, "no deployed copies checked"

        # agents/ deployed at all
        assert (dst / ".claude/agents").is_dir(), ".claude/agents not deployed"
    print("PASS test_deployed_copies_match_source")


def test_rabbit_project_command_scaffold_present():
    """The rabbit-project command scaffold is deployed."""
    with tempfile.TemporaryDirectory() as td:
        _install, dst = _install_into(Path(td).resolve())
        cmd = dst / ".claude/commands/rabbit-project.md"
        assert cmd.is_file(), "rabbit-project command scaffold not deployed"
    print("PASS test_rabbit_project_command_scaffold_present")


def test_no_dangling_references():
    """settings.json hook commands + every install-manifest destination point
    only at files that exist in the install — nothing dangling."""
    with tempfile.TemporaryDirectory() as td:
        install, dst = _install_into(Path(td).resolve())

        # (a) settings hook commands resolve to existing files.
        settings = json.loads((dst / ".claude/settings.json").read_text())
        for _event, cmd in _hook_command_strings(settings):
            hook_path = _resolve_hook_path(cmd, dst)
            assert hook_path.is_file(), (
                f"dangling hook command: {cmd!r} -> {hook_path}"
            )

        # (b) every manifest destination the installer copies exists.
        manifest_dsts = []
        manifest_dsts += list(install.SAME_PATH_FILES)
        manifest_dsts += [dst_rel for _s, dst_rel in install.HOOKS]
        manifest_dsts += [dst_rel for _s, dst_rel in install.SKILLS]
        manifest_dsts += [dst_rel for _s, dst_rel in install.AGENTS]
        manifest_dsts += [dst_rel for _s, dst_rel in install.COMMANDS]
        for feature, paths in install.FEATURE_INCLUDES.items():
            base = f".claude/features/{feature}"
            manifest_dsts += [f"{base}/{rel}" for rel in paths]
        for rel in manifest_dsts:
            assert (dst / rel).is_file(), (
                f"dangling manifest destination: {rel} absent from install"
            )
    print("PASS test_no_dangling_references")


def main() -> int:
    test_toplevel_closure_present()
    test_every_hook_path_exists_and_executable()
    test_every_feature_dir_has_valid_feature_json()
    test_deployed_copies_match_source()
    test_rabbit_project_command_scaffold_present()
    test_no_dangling_references()
    print("ALL PASSED test-install-e2e-ready-to-run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
