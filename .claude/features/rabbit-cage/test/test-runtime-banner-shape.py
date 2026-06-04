#!/usr/bin/env python3
"""test-runtime-banner-shape.py — e2e: issue #449.

session-start-dispatcher.py renders the welcome banner as a 3-row rabbit box
around the centered version, followed by a PLAIN (un-decorated) welcome line
and the existing policy summary sublines.

Target layout (each row carries the brand prefix `[🐇 rabbit 🐇]`):
  Row 1: brand prefix + top border of 32 🐇
  Row 2: brand prefix + 🐇 + `rabbit v<version>` centered + 🐇
  Row 3: brand prefix + bottom border of 32 🐇
  Then: brand prefix + `Welcome — governing policies loaded` (plain — no
        ━━━ bars, no ✅ icon)
  Then: the three policy summary sublines (philosophy/spec-rules/coding-rules)

Driven end-to-end through the real deployed dispatcher subprocess.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RABBIT_CAGE = REPO / ".claude/features/rabbit-cage"
SESSION_SRC = RABBIT_CAGE / "hooks/session-start-dispatcher.py"
DISPATCHER_LIB_SRC = RABBIT_CAGE / "hooks/_dispatcher_lib.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"

BOX_WIDTH = 32
RABBIT = "\U0001f407"
TOP = RABBIT * BOX_WIDTH


def _build_install_root(td: Path, *, version_text: str = "v9.9.9") -> Path:
    install_root = td / "rabbit_install"
    install_root.mkdir()

    hooks_dir = install_root / ".claude/hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy2(SESSION_SRC, hooks_dir / "session-start-dispatcher.py")
    shutil.copy2(DISPATCHER_LIB_SRC, hooks_dir / "_dispatcher_lib.py")

    (install_root / ".claude/features").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REPO / ".claude/features/contract",
        install_root / ".claude/features/contract",
    )
    shutil.copytree(
        REPO / ".claude/features/rabbit-meta",
        install_root / ".claude/features/rabbit-meta",
    )
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


def _run(install_root: Path) -> subprocess.CompletedProcess:
    dispatcher = install_root / ".claude/hooks/session-start-dispatcher.py"
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(install_root),
    )


def _system_message(stdout: str) -> str:
    stdout = stdout.strip()
    assert stdout, "expected JSON on stdout"
    return json.loads(stdout).get("systemMessage", "")


def _lines(sysmsg: str):
    clean = re.sub(r"\x1b\[[0-9;]*m", "", sysmsg)
    return [ln for ln in clean.split("\n") if ln.strip()]


def _display_width(text: str) -> int:
    """Display-column width counting the box rabbit (🐇, U+1F407) as 2 columns.

    Emoji render as ~2 terminal columns; every other char counts as 1. This
    is the common-case approximation the alignment fix targets (Inv 40 /
    issue #629); perfect width is terminal-dependent.
    """
    return sum(2 if ch == RABBIT else 1 for ch in text)


def test_three_row_box_around_centered_version():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, version_text="v1.2.3")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        lines = _lines(sysmsg)

        # Row 1: top border of 32 rabbits
        top_idx = next((i for i, ln in enumerate(lines) if TOP in ln), None)
        assert top_idx is not None, (
            f"top border ({BOX_WIDTH} rabbits) missing; got {lines!r}")

        # Row 2: version centered between two side rabbits
        ver_line = lines[top_idx + 1]
        assert "rabbit v1.2.3" in ver_line, (
            f"version row missing; got {ver_line!r}")
        inner = ver_line.split("]", 1)[1].strip()  # drop the brand prefix
        assert inner.startswith(RABBIT) and inner.endswith(RABBIT), (
            f"version row must be bordered by a rabbit each side; got {inner!r}")
        core = inner[len(RABBIT):-len(RABBIT)]
        left = len(core) - len(core.lstrip())
        right = len(core) - len(core.rstrip())
        assert left > 0 and right > 0, (
            f"version must be centered (padding both sides); got {core!r}")
        assert abs(left - right) <= 1, (
            f"version must be CENTERED (balanced padding); "
            f"got left={left} right={right}")

        # Row 3: bottom border of 32 rabbits
        bottom_line = lines[top_idx + 2]
        assert TOP in bottom_line, f"bottom border missing; got {bottom_line!r}"

    print("PASS test_three_row_box_around_centered_version")


def test_version_row_display_width_matches_border():
    """Issue #629 Defect 2: the version row's display width (counting each
    box 🐇 as 2 columns) MUST equal the border row's display width, so the
    closing 🐇 lands on the border column instead of drifting off it."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, version_text="v1.2.3")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        lines = _lines(sysmsg)

        top_idx = next((i for i, ln in enumerate(lines) if TOP in ln), None)
        assert top_idx is not None, f"top border missing; got {lines!r}"

        # Strip the brand prefix `[🐇 rabbit 🐇] ` so we compare only the box
        # region (the bordered row), which is what must align.
        border_inner = lines[top_idx].split("]", 1)[1].strip()
        ver_inner = lines[top_idx + 1].split("]", 1)[1].strip()

        bw = _display_width(border_inner)
        vw = _display_width(ver_inner)
        assert bw == vw, (
            f"version row display width must equal border display width; "
            f"border={bw} version={vw} (border={border_inner!r} "
            f"version={ver_inner!r})")
    print("PASS test_version_row_display_width_matches_border")


def test_welcome_line_is_plain():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, version_text="v1.2.3")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        lines = _lines(sysmsg)
        welcome = next((ln for ln in lines if "Welcome" in ln), None)
        assert welcome is not None, f"welcome line missing; got {lines!r}"
        assert "Welcome — governing policies loaded" in welcome, (
            f"welcome text changed; got {welcome!r}")
        # decoration stripped: no ━━━ bars, no ✅ icon
        assert "━" not in welcome, (
            f"welcome line still decorated with bars; got {welcome!r}")
        assert "✅" not in welcome, (
            f"welcome line still carries ✅ icon; got {welcome!r}")

    print("PASS test_welcome_line_is_plain")


def test_policy_sublines_unchanged():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, version_text="v1.2.3")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        for needle in ("philosophy.md", "spec-rules.md", "coding-rules.md"):
            assert needle in sysmsg, (
                f"policy subline {needle} missing; got {sysmsg!r}")
    print("PASS test_policy_sublines_unchanged")


def test_box_precedes_welcome():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, version_text="v1.2.3")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        box_idx = sysmsg.find(TOP)
        welcome_idx = sysmsg.find("Welcome")
        assert box_idx != -1 and welcome_idx != -1
        assert box_idx < welcome_idx, "box must precede welcome line"
    print("PASS test_box_precedes_welcome")


def main() -> int:
    test_three_row_box_around_centered_version()
    test_version_row_display_width_matches_border()
    test_welcome_line_is_plain()
    test_policy_sublines_unchanged()
    test_box_precedes_welcome()
    return 0


if __name__ == "__main__":
    sys.exit(main())
