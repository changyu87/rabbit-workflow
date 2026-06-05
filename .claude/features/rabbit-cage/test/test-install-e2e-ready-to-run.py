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

from __future__ import annotations

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


def _closure_src_rels(install_mod) -> list[str]:
    """Every repo-relative SOURCE path install.main() reads, in closure order.

    SAME_PATH_FILES + HOOKS + SKILLS + AGENTS + COMMANDS + FEATURE_INCLUDES.
    This is the single enumeration shared by the real-repo existence check
    (#880, de-circularization) and the sandbox builder, so the two can never
    drift apart.
    """
    rels: list[str] = list(install_mod.SAME_PATH_FILES)
    rels += [src for src, _dst in install_mod.HOOKS]
    rels += [src for src, _dst in install_mod.SKILLS]
    rels += [src for src, _dst in install_mod.AGENTS]
    rels += [src for src, _dst in install_mod.COMMANDS]
    for feature, paths in install_mod.FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        rels += [f"{base}/{rel}" for rel in paths]
    return rels


def _build_src_tree(src_root: Path, install_mod) -> None:
    """Copy every file install.main() needs from the real repo into src_root.

    Mirrors the closure main() reads (see _closure_src_rels). Sourcing only
    these from the clean repo tree keeps the sandbox a faithful stand-in for
    the extracted tarball.

    Pre-#880 this builder copied exactly install.SAME_PATH_FILES et al. and
    then ran install against that sandbox — a CIRCULAR check that validated
    install.py against its OWN list and could never observe a source the repo
    was missing. The de-circularization (test_closure_sources_exist_in_repo
    below) validates the closure against the REAL repo surface BEFORE any
    sandbox is built; this builder still copies the closure to exercise the
    real main() end to end.
    """
    for rel in _closure_src_rels(install_mod):
        s = REPO / rel
        d = src_root / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)


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

def test_closure_sources_exist_in_repo():
    """De-circularization (#880): every SOURCE the install closure declares
    EXISTS on disk in the REAL repo.

    This is the check the old sandbox-only flow could never make: it copied
    exactly the closure list then ran install against that copy, so a closure
    entry whose source the repo had retired (e.g. #853's deletion of
    rabbit-feature-audit/SKILL.md) was invisible. Here we resolve every
    closure source against the REAL repo tree and fail loud — naming the
    offending path — when one is absent. Delegates to install.py's own
    importable `check_install_sources_exist` so the contract gate (piece 2)
    and this E2E share one implementation.
    """
    install = _load_install()
    missing = install.check_install_sources_exist(REPO)
    assert missing == [], (
        "install closure references source files absent from the repo "
        "(dangling required-file -> fresh-install abort, #880):\n  "
        + "\n  ".join(missing)
    )
    print("PASS test_closure_sources_exist_in_repo")


def test_every_feature_deployed_surface_covered():
    """Every runtime-deployed surface each shipped feature publishes (its
    feature.json manifest `source` paths) is present in install.py's closure
    for that feature — no surface omitted from the install (#880).

    Pairs with test_closure_sources_exist_in_repo: that check proves no
    listed source is dangling; this one proves no published surface is
    MISSING from the list. Together they bound the closure on both sides
    against the real repo, replacing the circular sandbox-only validation.
    """
    install = _load_install()
    _PUBLISH_SOURCE_APIS = {
        "publish_hook", "publish_file", "publish_command",
        "publish_settings", "publish_skill",
    }
    uncovered: list[str] = []
    for feature, paths in install.FEATURE_INCLUDES.items():
        included = set(paths)
        fj = REPO / ".claude/features" / feature / "feature.json"
        if not fj.is_file():
            continue
        data = json.loads(fj.read_text())
        for entry in data.get("manifest") or []:
            if entry.get("api", "") not in _PUBLISH_SOURCE_APIS:
                continue
            src = (entry.get("args") or {}).get("source")
            if not isinstance(src, str) or not src:
                continue
            # Only feature-dir-relative sources are shipped via FEATURE_INCLUDES.
            if src.startswith("/") or src.startswith(".claude/"):
                continue
            if src not in included:
                uncovered.append(f"{feature}: {src}")
    assert uncovered == [], (
        "feature manifest declares deployed surfaces absent from install.py "
        "FEATURE_INCLUDES (omitted from the install):\n  "
        + "\n  ".join(uncovered)
    )
    print("PASS test_every_feature_deployed_surface_covered")


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
    # Run the real-repo closure checks FIRST: they validate install.py against
    # the actual repo surface and fail loud on a dangling/omitted source before
    # any sandbox is built (#880 de-circularization).
    test_closure_sources_exist_in_repo()
    test_every_feature_deployed_surface_covered()
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
