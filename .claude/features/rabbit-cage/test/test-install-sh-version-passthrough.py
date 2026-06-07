#!/usr/bin/env python3
"""test-install-sh-version-passthrough.py — bash-level smoke test that
install.sh exports RABBIT_INSTALLED_REF before invoking install.py, so the
.version pin written by install.py reflects the fetched ref instead of
always defaulting to "unknown" for one-liner installs (Inv 22e, Fixes #258).

Strategy: same shape as test-install-sh-update-flag.py — stub curl/tar via
a PATH-shadowed bin/, pre-populate the extracted source tree with a stub
install.py that records os.environ.get("RABBIT_INSTALLED_REF", "") to a
sidecar file. Then assert:
  (1) when RABBIT_REF is set, install.sh propagates it as
      RABBIT_INSTALLED_REF to install.py.
  (2) when both RABBIT_REF and RABBIT_INSTALLED_REF are set externally,
      the explicit RABBIT_INSTALLED_REF wins (override semantics from
      `${RABBIT_INSTALLED_REF:-$RABBIT_REF}`).
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


def _set_up_workspace(td: Path) -> tuple[Path, Path, Path]:
    """Create a workspace with install.sh, stub curl/tar, and a stub
    install.py that writes os.environ.get('RABBIT_INSTALLED_REF', '') into
    a sidecar file named `.rabbit-installed-ref-sidecar` under --target.
    """
    work = td / "work"
    work.mkdir()
    shutil.copy2(INSTALL_SH, work / "install.sh")
    os.chmod(work / "install.sh", 0o755)

    stub_bin = td / "stubbin"
    stub_bin.mkdir()

    extracted = td / "extracted"
    extracted.mkdir()
    src_dir = extracted / "rabbit-workflow-stub"
    src_dir.mkdir()
    sidecar = td / "sidecar.txt"
    # Stub install.py: parse --target arg, create the dir (so install.sh's
    # downstream commands don't fail), and write
    # os.environ.get('RABBIT_INSTALLED_REF', '') into a sidecar file.
    (src_dir / "install.py").write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "argv = sys.argv\n"
        "if '--target' in argv:\n"
        "    target = argv[argv.index('--target') + 1]\n"
        "    os.makedirs(target, exist_ok=True)\n"
        f"open({str(sidecar)!r}, 'w').write(os.environ.get('RABBIT_INSTALLED_REF', ''))\n"
        "sys.exit(0)\n"
    )
    os.chmod(src_dir / "install.py", 0o755)

    # Stub curl — no-op (touches the requested -o file so tar has input).
    curl_stub = stub_bin / "curl"
    curl_stub.write_text(
        "#!/usr/bin/env bash\n"
        "out=\"\"\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -o) out=\"$2\"; shift 2;;\n"
        "    -O) shift;;\n"
        "    *) shift;;\n"
        "  esac\n"
        "done\n"
        "if [ -n \"$out\" ]; then : > \"$out\"; fi\n"
        "exit 0\n"
    )
    os.chmod(curl_stub, 0o755)

    # Stub tar — copies pre-built src tree into $TMP via -C.
    tar_stub = stub_bin / "tar"
    tar_stub.write_text(
        "#!/usr/bin/env bash\n"
        "dest=\"\"\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -C) dest=\"$2\"; shift 2;;\n"
        "    *) shift;;\n"
        "  esac\n"
        "done\n"
        f"cp -a {str(src_dir)!s} \"$dest/rabbit-workflow-stub\"\n"
        "exit 0\n"
    )
    os.chmod(tar_stub, 0o755)

    return work, stub_bin, sidecar


def _run_install_sh(
    workdir: Path,
    stubbin: Path,
    extra_args: list[str],
    env_extra: dict | None = None,
) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{stubbin}:{env['PATH']}"
    # Wipe any inherited RABBIT_* vars so tests start clean.
    for k in list(env.keys()):
        if k.startswith("RABBIT_"):
            del env[k]
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["bash", str(workdir / "install.sh"), *extra_args],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_install_sh_propagates_rabbit_ref_as_installed_ref():
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_propagates_rabbit_ref_as_installed_ref (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, sidecar = _set_up_workspace(td_path)
        rc, out, err = _run_install_sh(
            work, stubbin, [], env_extra={"RABBIT_REF": "v1.2.3"}
        )
        assert rc == 0, f"install.sh exited {rc}: stderr={err!r}"
        assert sidecar.is_file(), (
            f"stub install.py was not invoked; install.sh stderr={err!r}"
        )
        content = sidecar.read_text()
        assert content == "v1.2.3", (
            f"install.sh must export RABBIT_INSTALLED_REF=$RABBIT_REF; "
            f"got sidecar={content!r}, expected 'v1.2.3'"
        )
    print("PASS test_install_sh_propagates_rabbit_ref_as_installed_ref")


def test_install_sh_honours_explicit_rabbit_installed_ref_override():
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_honours_explicit_rabbit_installed_ref_override (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, sidecar = _set_up_workspace(td_path)
        rc, out, err = _run_install_sh(
            work,
            stubbin,
            [],
            env_extra={
                "RABBIT_REF": "dev",
                "RABBIT_INSTALLED_REF": "explicit-label",
            },
        )
        assert rc == 0, f"install.sh exited {rc}: stderr={err!r}"
        assert sidecar.is_file()
        content = sidecar.read_text()
        assert content == "explicit-label", (
            f"explicit RABBIT_INSTALLED_REF must win over RABBIT_REF; "
            f"got sidecar={content!r}, expected 'explicit-label'"
        )
    print("PASS test_install_sh_honours_explicit_rabbit_installed_ref_override")


def main() -> int:
    test_install_sh_propagates_rabbit_ref_as_installed_ref()
    test_install_sh_honours_explicit_rabbit_installed_ref_override()
    return 0


if __name__ == "__main__":
    sys.exit(main())
