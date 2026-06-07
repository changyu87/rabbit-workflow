#!/usr/bin/env python3
"""test-install-ships-skill-referenced-scripts.py — end-to-end fresh-install
proof that every SKILL-referenced backing script actually lands on disk.

Regression #897: rabbit-decompose's SKILL.md Step 4 invokes
`.claude/features/rabbit-decompose/scripts/handoff-scaffold.py` (added by #890),
but install.py's FEATURE_INCLUDES['rabbit-decompose'] was not updated to ship
it. A fresh `curl ... | bash` install therefore omitted the script, and Step 4
failed at runtime with `No such file or directory`.

The companion unit test `test-feature-includes-scripts-closure.py` (Inv 24)
catches the closure gap statically against FEATURE_INCLUDES. This e2e test is
the independent end-to-end complement: it runs the REAL user-facing installer
`install.main()` (the same call install.sh makes after extracting the upstream
tarball) into a throwaway sandbox, then asserts every script the DEPLOYED
SKILL bodies reference is present AND executable in the install — derived from
the SKILL bodies, NOT from FEATURE_INCLUDES, so an omission from the closure is
observed as a genuine missing-on-disk failure rather than a list mismatch.

Self-cleaning (the sandbox is a tempfile.TemporaryDirectory discarded on exit).
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

# Matches literal paths like .claude/features/<feature>/scripts/<script>.py
SCRIPT_REF_RE = re.compile(r"\.claude/features/([\w-]+)/scripts/([\w.-]+\.py)")


def _load_install():
    spec = importlib.util.spec_from_file_location(
        "install_skill_scripts_under_test", INSTALL_PY
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _closure_src_rels(install_mod) -> list[str]:
    """Every repo-relative SOURCE path install.main() reads, in closure order.

    Mirrors test-install-e2e-ready-to-run.py._closure_src_rels so the sandbox
    is a faithful stand-in for the extracted tarball.
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
    for rel in _closure_src_rels(install_mod):
        s = REPO / rel
        d = src_root / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)


def _run_install(install_mod, src: Path, dst: Path) -> int:
    saved = sys.argv
    sys.argv = ["install.py", "--src", str(src), "--target", str(dst)]
    try:
        return install_mod.main()
    finally:
        sys.argv = saved


def _install_into(td: Path):
    install = _load_install()
    src = td / "src"
    src.mkdir()
    _build_src_tree(src, install)
    dst = td / "dst"
    rc = _run_install(install, src, dst)
    assert rc == 0, f"install.main() returned {rc}"
    return install, dst


def _skill_referenced_scripts(install_mod) -> set[tuple[str, str]]:
    """Return {(feature, script_basename)} every SKILL in install's SKILLS list
    references via a literal .claude/features/<feature>/scripts/<script>.py path.

    Read from the REPO source SKILL bodies (the bodies the install ships
    verbatim), so the expectation is derived independently of FEATURE_INCLUDES.
    """
    refs: set[tuple[str, str]] = set()
    for src_rel, _dst_rel in install_mod.SKILLS:
        skill_abs = REPO / src_rel
        if not skill_abs.is_file():
            continue
        refs |= set(SCRIPT_REF_RE.findall(skill_abs.read_text()))
    return refs


def test_fresh_install_ships_every_skill_referenced_script():
    """Every script the deployed SKILL bodies reference lands on disk in a fresh
    install AND is executable (it will actually run when the skill shells out)."""
    install_mod = _load_install()
    refs = _skill_referenced_scripts(install_mod)
    assert refs, "no SKILL-referenced scripts discovered (regex/closure broke)"

    with tempfile.TemporaryDirectory() as td:
        _install, dst = _install_into(Path(td).resolve())
        missing: list[str] = []
        for feature, script in sorted(refs):
            rel = f".claude/features/{feature}/scripts/{script}"
            on_disk = dst / rel
            if not on_disk.is_file():
                missing.append(rel)
            elif not os.access(on_disk, os.X_OK):
                missing.append(f"{rel} (present but NOT executable)")
        assert missing == [], (
            "fresh install omitted SKILL-referenced backing scripts "
            "(regression #897 class — Step 4 fails at runtime with "
            "'No such file or directory'):\n  " + "\n  ".join(missing)
        )

    # Regression anchor: the specific #897 script must be among those proven.
    assert ("rabbit-decompose", "handoff-scaffold.py") in refs, (
        "rabbit-decompose SKILL no longer references handoff-scaffold.py; "
        "update this anchor if Step 4 retired the script (see #897)"
    )
    print("PASS test_fresh_install_ships_every_skill_referenced_script")


def main() -> int:
    test_fresh_install_ships_every_skill_referenced_script()
    print("ALL PASSED test-install-ships-skill-referenced-scripts.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
