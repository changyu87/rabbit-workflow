#!/usr/bin/env python3
"""test-install-sh-resolves-latest-release.py — install.sh default ref resolves the
LATEST published release DYNAMICALLY (Inv 26, #848).

Two layers:
  (A) STATIC source-inspection: install.sh references the releases/latest endpoint,
      declares a RABBIT_FALLBACK_REF semver-tag literal (not 'dev'), and keeps
      RABBIT_REF as an explicit override.
  (B) END-TO-END via a PATH-shadowed stub curl that (i) serves a mocked
      releases/latest JSON body when asked for the API URL, (ii) records the
      archive URL it is asked to download into a sidecar, and (iii) can be made
      to FAIL the latest-lookup to exercise the offline fallback. The stub tar
      copies a pre-built source tree carrying a recorder install.py. We assert
      the ref actually fetched (parsed from the recorded archive URL):
        - no RABBIT_REF, latest lookup OK    -> mocked latest tag
        - explicit RABBIT_REF=<x>            -> <x> verbatim (lookup short-circuited)
        - no RABBIT_REF, latest lookup FAILS -> RABBIT_FALLBACK_REF
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_SH = REPO / "install.sh"

MOCK_LATEST = "v9.0.26"
ARCHIVE_RE = re.compile(r"/archive/(?P<ref>.+)\.tar\.gz$")

pass_n = 0
fail_n = 0


def ok(msg):
    global pass_n
    print(f"  PASS: {msg}")
    pass_n += 1


def bad(msg):
    global fail_n
    print(f"  FAIL: {msg}")
    fail_n += 1


# ── Layer A: static source inspection ──────────────────────────────────────
def static_checks():
    src = INSTALL_SH.read_text()

    if "releases/latest" in src:
        ok("install.sh references the releases/latest endpoint (dynamic default)")
    else:
        bad("install.sh does not reference releases/latest (no dynamic default)")

    m = re.search(r'RABBIT_FALLBACK_REF="(?P<v>[^"]+)"', src)
    if m is None:
        bad("install.sh declares no RABBIT_FALLBACK_REF literal")
    else:
        val = m.group("v")
        if re.match(r"^v[0-9]+\.[0-9]+\.[0-9]+$", val):
            ok(f"RABBIT_FALLBACK_REF is a semver tag: {val!r}")
        else:
            bad(f"RABBIT_FALLBACK_REF {val!r} is not a vX.Y.Z semver tag")
        if val == "dev":
            bad("RABBIT_FALLBACK_REF is the literal 'dev' (FORBIDDEN)")
        else:
            ok("RABBIT_FALLBACK_REF is not 'dev'")

    if 'RABBIT_REF:' in src or '${RABBIT_REF' in src or 'RABBIT_REF}' in src:
        ok("install.sh still honors an explicit RABBIT_REF override")
    else:
        bad("install.sh no longer references RABBIT_REF (override path lost)")


# ── Layer B: e2e via stub curl/tar ─────────────────────────────────────────
def _set_up_workspace(td: Path):
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
    # Recorder install.py: create --target dir so downstream cmds don't fail.
    (src_dir / "install.py").write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "argv = sys.argv\n"
        "if '--target' in argv:\n"
        "    os.makedirs(argv[argv.index('--target') + 1], exist_ok=True)\n"
        "sys.exit(0)\n"
    )
    os.chmod(src_dir / "install.py", 0o755)

    archive_log = td / "archive_url.txt"
    latest_json = td / "latest.json"
    latest_json.write_text('{"tag_name": "%s"}\n' % MOCK_LATEST)

    return work, stub_bin, src_dir, archive_log, latest_json


def _write_curl_stub(stub_bin: Path, src_dir: Path, archive_log: Path,
                     latest_json: Path, fail_latest: bool):
    # curl is called two ways by install.sh:
    #   (1) latest-release API lookup against .../releases/latest
    #   (2) archive download with -o <file> against .../archive/<ref>.tar.gz
    # The stub distinguishes by URL substring. fail_latest -> exit 1 on (1).
    py = (
        "#!/usr/bin/env python3\n"
        "import sys, shutil, re\n"
        f"FAIL_LATEST = {fail_latest!r}\n"
        f"LATEST_JSON = {str(latest_json)!r}\n"
        f"ARCHIVE_LOG = {str(archive_log)!r}\n"
        "args = sys.argv[1:]\n"
        "out = None\n"
        "url = None\n"
        "i = 0\n"
        "while i < len(args):\n"
        "    a = args[i]\n"
        "    if a == '-o':\n"
        "        out = args[i+1]; i += 2; continue\n"
        "    if a == '-O':\n"
        "        i += 1; continue\n"
        "    if a.startswith('-'):\n"
        "        # flag possibly w/ value we don't care about; if next looks like\n"
        "        # a URL it'll be caught below, otherwise treat as a bare flag.\n"
        "        i += 1; continue\n"
        "    if a.startswith('http'):\n"
        "        url = a\n"
        "    i += 1\n"
        "if url and 'releases/latest' in url:\n"
        "    if FAIL_LATEST:\n"
        "        sys.exit(22)\n"
        "    sys.stdout.write(open(LATEST_JSON).read())\n"
        "    sys.exit(0)\n"
        "if url and '/archive/' in url:\n"
        "    open(ARCHIVE_LOG, 'w').write(url)\n"
        "    if out:\n"
        "        open(out, 'w').close()\n"
        "    sys.exit(0)\n"
        "# Unknown curl invocation: succeed quietly (best-effort stub).\n"
        "if out:\n"
        "    open(out, 'w').close()\n"
        "sys.exit(0)\n"
    )
    curl_stub = stub_bin / "curl"
    curl_stub.write_text(py)
    os.chmod(curl_stub, 0o755)


def _write_tar_stub(stub_bin: Path, src_dir: Path):
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


def _run_install_sh(workdir: Path, stubbin: Path, env_extra: dict | None = None):
    env = os.environ.copy()
    env["PATH"] = f"{stubbin}:{env['PATH']}"
    for k in list(env.keys()):
        if k.startswith("RABBIT_"):
            del env[k]
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["bash", str(workdir / "install.sh")],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _fetched_ref(archive_log: Path) -> str | None:
    if not archive_log.is_file():
        return None
    m = ARCHIVE_RE.search(archive_log.read_text().strip())
    return m.group("ref") if m else None


def e2e_default_resolves_latest():
    if shutil.which("bash") is None:
        print("  SKIP e2e_default_resolves_latest (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, src_dir, archive_log, latest_json = _set_up_workspace(td_path)
        _write_curl_stub(stubbin, src_dir, archive_log, latest_json, fail_latest=False)
        _write_tar_stub(stubbin, src_dir)
        rc, out, err = _run_install_sh(work, stubbin)
        if rc != 0:
            bad(f"default install.sh exited {rc}: stderr={err!r}")
            return
        ref = _fetched_ref(archive_log)
        if ref == MOCK_LATEST:
            ok(f"default path fetched the mocked latest tag {MOCK_LATEST!r}")
        else:
            bad(f"default path fetched ref={ref!r}, expected mocked latest {MOCK_LATEST!r}")


def e2e_explicit_ref_short_circuits():
    if shutil.which("bash") is None:
        print("  SKIP e2e_explicit_ref_short_circuits (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, src_dir, archive_log, latest_json = _set_up_workspace(td_path)
        _write_curl_stub(stubbin, src_dir, archive_log, latest_json, fail_latest=False)
        _write_tar_stub(stubbin, src_dir)
        rc, out, err = _run_install_sh(work, stubbin, env_extra={"RABBIT_REF": "v1.2.3"})
        if rc != 0:
            bad(f"explicit-ref install.sh exited {rc}: stderr={err!r}")
            return
        ref = _fetched_ref(archive_log)
        if ref == "v1.2.3":
            ok("explicit RABBIT_REF short-circuits the dynamic lookup (v1.2.3 fetched)")
        else:
            bad(f"explicit RABBIT_REF must win; fetched ref={ref!r}, expected 'v1.2.3'")


def e2e_offline_falls_back():
    if shutil.which("bash") is None:
        print("  SKIP e2e_offline_falls_back (bash not on PATH)")
        return
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        work, stubbin, src_dir, archive_log, latest_json = _set_up_workspace(td_path)
        _write_curl_stub(stubbin, src_dir, archive_log, latest_json, fail_latest=True)
        _write_tar_stub(stubbin, src_dir)
        rc, out, err = _run_install_sh(work, stubbin)
        if rc != 0:
            bad(f"offline-fallback install.sh exited {rc}: stderr={err!r}")
            return
        # The hardcoded fallback literal in install.sh.
        m = re.search(r'RABBIT_FALLBACK_REF="([^"]+)"', INSTALL_SH.read_text())
        fallback = m.group(1) if m else None
        ref = _fetched_ref(archive_log)
        if ref == fallback and fallback is not None:
            ok(f"offline lookup falls back to RABBIT_FALLBACK_REF {fallback!r}")
        else:
            bad(f"offline path fetched ref={ref!r}, expected fallback {fallback!r}")
        if "fallback" in (err or "").lower() or (fallback and fallback in (err or "")):
            ok("offline path emitted a clear stderr fallback message")
        else:
            bad(f"offline path did not emit a clear fallback stderr line; stderr={err!r}")


def main() -> int:
    print("test-install-sh-resolves-latest-release.py")
    static_checks()
    e2e_default_resolves_latest()
    e2e_explicit_ref_short_circuits()
    e2e_offline_falls_back()
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
