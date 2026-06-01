#!/usr/bin/env python3
"""test-install-sh-error-points-to-install-py.py — pins the survivor-command
pointer in install.sh's .rabbit/-exists refusal (Inv 22a, Fixes #273).

When a user runs `bash install.sh` against a directory that already contains
a .rabbit/ install, install.sh refuses and the error message MUST tell the
user how to update: `python3 .rabbit/install.py --update`. Without this
pointer, users have no way to discover the survivor path after --update was
retired from install.sh.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_SH = REPO / "install.sh"


def test_install_sh_refusal_points_to_install_py_update():
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_refusal_points_to_install_py_update (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work = td_path / "work"
        work.mkdir()
        shutil.copy2(INSTALL_SH, work / "install.sh")
        os.chmod(work / "install.sh", 0o755)
        (work / ".rabbit").mkdir()

        proc = subprocess.run(
            ["bash", str(work / "install.sh")],
            cwd=str(work),
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0, (
            f"install.sh against pre-existing .rabbit/ must refuse; got rc={proc.returncode}"
        )
        combined = proc.stdout + proc.stderr
        assert "python3 .rabbit/install.py --update" in combined, (
            "install.sh refusal MUST point users at the survivor update path "
            "`python3 .rabbit/install.py --update`; got "
            f"stdout={proc.stdout!r}, stderr={proc.stderr!r}"
        )
    print("PASS test_install_sh_refusal_points_to_install_py_update")


def main() -> int:
    test_install_sh_refusal_points_to_install_py_update()
    return 0


if __name__ == "__main__":
    sys.exit(main())
