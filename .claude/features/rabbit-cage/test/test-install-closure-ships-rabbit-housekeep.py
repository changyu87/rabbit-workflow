#!/usr/bin/env python3
"""test-install-closure-ships-rabbit-housekeep.py — install closure ships
rabbit-housekeep (#1181).

Regression #1181 (root cause of #1179): install.py's hardcoded vendored-install
closure (SKILLS, COMMANDS, FEATURE_INCLUDES) entirely omitted rabbit-housekeep.
A fresh `curl … install.sh | bash` / plugin install therefore shipped NO
rabbit-housekeep SKILL.md, no `/rabbit-housekeep` command, no feature.json, and
no backing scripts — the user-facing surface added at SOURCE by #1180 was
absent from every vendored install.

The generic closure tests (test-install-ships-skill-referenced-scripts.py,
test-feature-includes-scripts-closure.py) derive their expectations from the
SHIPPED surfaces only, so a feature that is wholly ABSENT from the closure is
invisible to them — they cannot observe the omission. This test pins the
positive expectation directly: the rabbit-housekeep SKILL and command are in
SKILLS/COMMANDS, and FEATURE_INCLUDES['rabbit-housekeep'] ships the feature.json,
the SKILL.md, the command .md, and every backing script the deployed surface
references — each pointing at a file that exists on disk.

Once rabbit-housekeep is in SKILLS + COMMANDS, the generic Inv 24 / #897 / #1035
tests independently enforce the script-closure completeness; this test guards
against the feature being dropped from the closure again.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(subprocess.run(
    ["git", "-C", str(SCRIPT_DIR), "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip())
INSTALL_PY = REPO_ROOT / ".claude/features/rabbit-cage/install.py"

# The backing scripts the deployed rabbit-housekeep surface (SKILL.md + command)
# references and that exist on disk — the authoritative ship set.
EXPECTED_SCRIPTS = [
    "scripts/measure-reduction.py",
    "scripts/check-script-backed.py",
    "scripts/resolve-housekeep-scope.py",
    "scripts/wave-automerge.py",
]


def _load_install():
    spec = importlib.util.spec_from_file_location("install_housekeep_check", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_skill_shipped():
    mod = _load_install()
    src = ".claude/features/rabbit-housekeep/skills/rabbit-housekeep/SKILL.md"
    dst = ".claude/skills/rabbit-housekeep/SKILL.md"
    assert (src, dst) in mod.SKILLS, (
        "install.py SKILLS must ship rabbit-housekeep's SKILL.md so a vendored "
        f"install deploys the skill (#1181); missing entry ({src!r}, {dst!r})"
    )
    assert (REPO_ROOT / src).is_file(), f"SKILL source missing on disk: {src}"
    print("PASS test_skill_shipped")


def test_command_shipped():
    mod = _load_install()
    src = ".claude/features/rabbit-housekeep/commands/rabbit-housekeep.md"
    dst = ".claude/commands/rabbit-housekeep.md"
    assert (src, dst) in mod.COMMANDS, (
        "install.py COMMANDS must ship the /rabbit-housekeep command so a "
        f"vendored install deploys it (#1181); missing entry ({src!r}, {dst!r})"
    )
    assert (REPO_ROOT / src).is_file(), f"command source missing on disk: {src}"
    print("PASS test_command_shipped")


def test_feature_includes_shipped():
    mod = _load_install()
    includes = mod.FEATURE_INCLUDES.get("rabbit-housekeep")
    assert includes is not None, (
        "FEATURE_INCLUDES must contain a 'rabbit-housekeep' entry so the "
        "feature's feature.json, skill, command, and backing scripts ship in a "
        "vendored install (#1181)"
    )
    base = REPO_ROOT / ".claude/features/rabbit-housekeep"
    required = [
        "feature.json",
        "skills/rabbit-housekeep/SKILL.md",
        "commands/rabbit-housekeep.md",
        *EXPECTED_SCRIPTS,
    ]
    missing_from_list = [r for r in required if r not in includes]
    assert missing_from_list == [], (
        "FEATURE_INCLUDES['rabbit-housekeep'] omits required shipped files "
        f"(#1181):\n  " + "\n  ".join(missing_from_list)
    )
    missing_on_disk = [r for r in includes if not (base / r).is_file()]
    assert missing_on_disk == [], (
        "FEATURE_INCLUDES['rabbit-housekeep'] names files absent on disk "
        "(dangling closure entry -> fresh-install abort, #880):\n  "
        + "\n  ".join(missing_on_disk)
    )
    print("PASS test_feature_includes_shipped")


def main() -> int:
    test_skill_shipped()
    test_command_shipped()
    test_feature_includes_shipped()
    print("ALL PASSED test-install-closure-ships-rabbit-housekeep.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
