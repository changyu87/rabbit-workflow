#!/usr/bin/env python3
"""test-install-sh-update-flag.py — bash-level smoke test that install.sh
forwards --update to install.py, via the explicit `--update` flag OR via
the `RABBIT_UPDATE=true` env-var equivalent (Inv 22).

Strategy: copy the real install.sh into a temp dir, but stub the network
fetch by pre-populating the extracted source directory and overriding
curl/tar via a PATH-shadowed stub. The stubbed install.py just dumps its
argv to a sidecar file so the test can grep for `--update`.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_SH = REPO / "install.sh"


def _set_up_workspace(td: Path) -> tuple[Path, Path, Path]:
    """Create a workspace with:
      - install.sh (copied from REPO),
      - stub bin/ containing curl and tar (both no-ops),
      - pre-extracted source under TMP/rabbit-workflow-stub/install.py that
        records argv and exits 0.

    The stub install.sh runs `python3 $SRC/install.py --src $SRC --target
    $(pwd)/.rabbit [--update]`. We intercept this by writing a fake install.py
    inside the pre-extracted source dir that writes its argv to argv-log.
    """
    work = td / "work"
    work.mkdir()
    shutil.copy2(INSTALL_SH, work / "install.sh")
    os.chmod(work / "install.sh", 0o755)

    stub_bin = td / "stubbin"
    stub_bin.mkdir()

    # Pre-extracted source the install.sh will discover via the
    # `find $TMP -maxdepth 1 -type d -name "rabbit-workflow-*"` line.
    # We make the script copy it into $TMP itself via a stubbed tar.
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

    # Stub curl: ignore url, do nothing (the tarball isn't actually downloaded).
    curl_stub = stub_bin / "curl"
    curl_stub.write_text(
        "#!/usr/bin/env bash\n"
        "# stub curl — no-op so install.sh's `curl ... -o TMP/rabbit.tar.gz`\n"
        "# succeeds without touching the network. We touch the tarball path\n"
        "# (last arg after -o or -O if present) so the next `tar` call has a\n"
        "# file to consume.\n"
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

    # Stub tar: instead of extracting, copy our pre-built source dir into the
    # destination passed via -C. install.sh calls `tar -xzf $TMP/rabbit.tar.gz
    # -C $TMP`; we intercept and copy `extracted/rabbit-workflow-stub` to
    # `$TMP/rabbit-workflow-stub`.
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


def _run_install_sh(workdir: Path, stubbin: Path, extra_args: list[str], env_extra: dict | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{stubbin}:{env['PATH']}"
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


def test_install_sh_forwards_update_flag():
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_forwards_update_flag (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, argv_log = _set_up_workspace(td_path)
        # Pre-populate .rabbit/ so we exercise the --update branch that
        # skips the early refusal. Without --update, install.sh refuses.
        (work / ".rabbit").mkdir()
        rc, out, err = _run_install_sh(work, stubbin, ["--update"])
        assert rc == 0, f"install.sh --update exited {rc}: stderr={err!r}"
        assert argv_log.is_file(), (
            f"stub install.py was not invoked; install.sh stderr={err!r}"
        )
        log = argv_log.read_text()
        assert "--update" in log, (
            f"install.sh did not forward --update to install.py; "
            f"argv-log={log!r}"
        )
    print("PASS test_install_sh_forwards_update_flag")


def test_install_sh_honours_rabbit_update_env_var():
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_honours_rabbit_update_env_var (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, argv_log = _set_up_workspace(td_path)
        (work / ".rabbit").mkdir()
        rc, out, err = _run_install_sh(
            work, stubbin, [], env_extra={"RABBIT_UPDATE": "true"}
        )
        assert rc == 0, f"install.sh RABBIT_UPDATE=true exited {rc}: stderr={err!r}"
        assert argv_log.is_file()
        log = argv_log.read_text()
        assert "--update" in log, (
            f"RABBIT_UPDATE=true did not produce --update on install.py argv; "
            f"argv-log={log!r}"
        )
    print("PASS test_install_sh_honours_rabbit_update_env_var")


def test_install_sh_refuses_without_update_when_dot_rabbit_exists():
    if shutil.which("bash") is None:
        print("SKIP test_install_sh_refuses_without_update_when_dot_rabbit_exists (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, argv_log = _set_up_workspace(td_path)
        (work / ".rabbit").mkdir()
        rc, out, err = _run_install_sh(work, stubbin, [])
        assert rc != 0, (
            "install.sh without --update must refuse when .rabbit/ exists; "
            f"got rc={rc}, stdout={out!r}"
        )
        assert not argv_log.exists(), (
            "stub install.py should not have been invoked under refusal"
        )
    print("PASS test_install_sh_refuses_without_update_when_dot_rabbit_exists")


def main() -> int:
    test_install_sh_refuses_without_update_when_dot_rabbit_exists()
    test_install_sh_forwards_update_flag()
    test_install_sh_honours_rabbit_update_env_var()
    return 0


if __name__ == "__main__":
    sys.exit(main())
