#!/usr/bin/env python3
"""test-install-update-rejects-non-rabbit-target.py — e2e: when --update is set
and --target is inferred from a directory that does NOT contain both .claude/
and .version, install.py refuses with exit 1 and a clear stderr message
(Inv 22g).
"""

from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install_at(path: Path):
    spec = importlib.util.spec_from_file_location("install_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_install(install_mod, argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    saved = sys.argv
    sys.argv = argv
    try:
        with redirect_stderr(buf):
            rc = install_mod.main()
    finally:
        sys.argv = saved
    return rc, buf.getvalue()


def test_update_rejects_target_without_claude_or_version():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        # Create a non-rabbit directory: just install.py, NO .claude/, NO .version.
        bogus = td_path / "bogus"
        bogus.mkdir()
        shutil.copy2(INSTALL_PY, bogus / "install.py")

        # Fixture --src so we exercise the inferred-target sanity check, not
        # the self-fetch network branch.
        fixture = td_path / "fixture"
        fixture.mkdir()

        mod = _load_install_at(bogus / "install.py")
        rc, err = _run_install(mod, ["install.py", "--update", "--src", str(fixture)])
        assert rc == 1, f"expected exit 1 when inferred target lacks .claude/+.version; got rc={rc}"
        # Stderr message must clearly identify the issue.
        assert "inferred" in err, f"stderr must mention inferred target; got: {err!r}"
        assert "rabbit install root" in err, (
            f"stderr must mention 'rabbit install root'; got: {err!r}"
        )
    print("PASS test_update_rejects_target_without_claude_or_version")


def main() -> int:
    test_update_rejects_target_without_claude_or_version()
    return 0


if __name__ == "__main__":
    sys.exit(main())
