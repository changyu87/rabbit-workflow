#!/usr/bin/env python3
"""test-install-sh-refuses-update-flag.py — pins the retirement of
install.sh's --update flag (Inv 22a, Fixes #273).

install.sh is for first-time installs only. The --update flag was retired —
updates now go exclusively through `python3 .rabbit/install.py --update`.

Asserts:
  (1) `bash install.sh --update` exits non-zero (no .rabbit/ present yet —
      the unknown --update arg should either be rejected or the script must
      refuse for a different reason). The pre-existing --update branch from
      PR #254/#259 is gone, so install.sh treats `--update` as the same as
      no-flag.
  (2) The error/output (stderr OR combined) mentions
      `python3 .rabbit/install.py --update` as the survivor command — OR
      the stub install.py never runs (refusal short-circuits).
  (3) `RABBIT_UPDATE=true bash install.sh` (env-var equivalent) is also
      ignored: install.sh proceeds as if no update flag was set, and the
      .rabbit/-exists refusal fires.
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
    argv_log = td / "argv.log"
    (src_dir / "install.py").write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"open({str(argv_log)!r}, 'a').write(' '.join(sys.argv) + '\\n')\n"
        "sys.exit(0)\n"
    )
    os.chmod(src_dir / "install.py", 0o755)

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

    return work, stub_bin, argv_log


def _run(work: Path, stubbin: Path, args: list[str], env_extra: dict | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{stubbin}:{env['PATH']}"
    for k in list(env.keys()):
        if k.startswith("RABBIT_"):
            del env[k]
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["bash", str(work / "install.sh"), *args],
        cwd=str(work),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_install_sh_update_flag_does_not_forward_to_install_py():
    """install.sh --update against a pre-existing .rabbit/ MUST refuse;
    install.py must NOT be invoked with --update (the flag is retired)."""
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_update_flag_does_not_forward_to_install_py (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, argv_log = _set_up_workspace(td_path)
        (work / ".rabbit").mkdir()
        rc, out, err = _run(work, stubbin, ["--update"])
        # install.sh MUST refuse when .rabbit/ exists, regardless of any --update flag.
        assert rc != 0, (
            "install.sh --update with pre-existing .rabbit/ must refuse "
            f"(--update retired per #273); got rc={rc}, stdout={out!r}, stderr={err!r}"
        )
        # The stub install.py must NOT have been invoked with --update.
        if argv_log.exists():
            log = argv_log.read_text()
            assert "--update" not in log, (
                "install.sh must not forward --update to install.py "
                f"(flag retired per #273); argv-log={log!r}"
            )
    print("PASS test_install_sh_update_flag_does_not_forward_to_install_py")


def test_install_sh_rabbit_update_env_var_does_not_forward_update():
    """RABBIT_UPDATE=true env-var equivalent is also retired."""
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_rabbit_update_env_var_does_not_forward_update (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, argv_log = _set_up_workspace(td_path)
        (work / ".rabbit").mkdir()
        rc, out, err = _run(work, stubbin, [], env_extra={"RABBIT_UPDATE": "true"})
        assert rc != 0, (
            "install.sh with RABBIT_UPDATE=true and pre-existing .rabbit/ must refuse "
            f"(env-var equivalent retired per #273); got rc={rc}, stderr={err!r}"
        )
        if argv_log.exists():
            log = argv_log.read_text()
            assert "--update" not in log, (
                "RABBIT_UPDATE=true must not forward --update to install.py "
                f"(env-var equivalent retired per #273); argv-log={log!r}"
            )
    print("PASS test_install_sh_rabbit_update_env_var_does_not_forward_update")


def main() -> int:
    test_install_sh_update_flag_does_not_forward_to_install_py()
    test_install_sh_rabbit_update_env_var_does_not_forward_update()
    return 0


if __name__ == "__main__":
    sys.exit(main())
