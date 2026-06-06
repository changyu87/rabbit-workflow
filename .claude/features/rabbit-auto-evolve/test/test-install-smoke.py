#!/usr/bin/env python3
"""test-install-smoke.py — tests for scripts/install-smoke.py (Inv 66).

The pre-merge install smoke (issue #966) runs an isolated, network-free
fresh-install + update smoke of rabbit-cage's install.py against the current
tree, so install/closure breakage is caught BEFORE a PR merges.

Coverage:
  - PASS on a clean tree: against the REAL repo root the smoke exits 0 (a
    real fresh install + update to tmp succeeds). This is the e2e variant.
  - FAIL on a simulated install failure: a shim install.py that exits
    non-zero makes the smoke report FAILURE (non-zero exit).
  - FAIL on a publish_file source-not-found signature even when the shim
    install.py exits 0 (the #969-style failure that prints an error but does
    not propagate a non-zero exit).
  - FAIL on an --update closure-shrink failure (the #968-style failure: the
    fresh install succeeds, the --update invocation fails).
  - SKIP (exit 0) when install.py cannot be found (degenerate self-build /
    isolated tempdir) — the resilient skip matching contract Inv 64/65.
  - --help smoke: exit 0 with recognizable usage text.

Shim install.py scripts are written into a tempdir and injected via the
RABBIT_AUTO_EVOLVE_INSTALL_PY env var; no live install / no network.
"""

import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "install-smoke.py")
)
# repo root: .../.claude/features/rabbit-auto-evolve/test -> up 4
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _run(env=None, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, env=env,
    )


def _write_shim(shim_dir, body):
    """Write an executable shim install.py with the given python `body`.
    Returns its path."""
    path = os.path.join(shim_dir, "install.py")
    with open(path, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write(body)
    os.chmod(path, stat.S_IRWXU)
    return path


def _env_with_shim(shim_path):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_INSTALL_PY"] = shim_path
    return env


# ---------------------------------------------------------------------------
# --help smoke
# ---------------------------------------------------------------------------
proc = _run(None, "--help")
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail(f"help: 'usage' missing; out={proc.stdout!r} err={proc.stderr!r}")
else:
    ok("help: usage text present")


# ---------------------------------------------------------------------------
# PASS on a clean tree (e2e: real install.py, real repo root, real fresh +
# update install to tmp). Always-on, offline (explicit --src), fast.
# ---------------------------------------------------------------------------
proc = _run(None, "--repo-root", REPO_ROOT)
if proc.returncode != 0:
    fail(f"clean-tree: real smoke should pass; got exit {proc.returncode}; "
         f"stderr={proc.stderr!r}")
else:
    ok("clean-tree: real fresh+update install smoke passes on the real tree")


# ---------------------------------------------------------------------------
# FAIL when the (shim) install.py exits non-zero on the FRESH install.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    shim = _write_shim(td, "import sys\n"
                           "sys.stderr.write('boom\\n')\n"
                           "sys.exit(3)\n")
    proc = _run(_env_with_shim(shim), "--repo-root", REPO_ROOT)
    if proc.returncode == 0:
        fail("fresh-nonzero: non-zero install exit should fail the smoke")
    elif "fresh" not in proc.stderr.lower():
        fail(f"fresh-nonzero: stderr should name 'fresh'; got {proc.stderr!r}")
    else:
        ok("fresh-nonzero: non-zero fresh install fails the smoke")


# ---------------------------------------------------------------------------
# FAIL on a publish_file source-not-found signature even with exit 0
# (the #969-style failure: prints an error but exits 0).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    shim = _write_shim(
        td,
        "import sys\n"
        "print('error: publish_file: source not found: foo/bar.md')\n"
        "sys.exit(0)\n",
    )
    proc = _run(_env_with_shim(shim), "--repo-root", REPO_ROOT)
    if proc.returncode == 0:
        fail("source-not-found: source-not-found output should fail the smoke "
             "even on exit 0")
    else:
        ok("source-not-found: 'source not found' output fails the smoke "
           "despite exit 0")


# ---------------------------------------------------------------------------
# FAIL on an --update closure-shrink failure (the #968-style failure:
# the FRESH install succeeds, the --update invocation fails).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    # The shim succeeds on a plain install, fails on --update.
    shim = _write_shim(
        td,
        "import sys\n"
        "if '--update' in sys.argv:\n"
        "    sys.stderr.write('error: closure error on --update\\n')\n"
        "    sys.exit(1)\n"
        "print('Installed 1 files')\n"
        "sys.exit(0)\n",
    )
    proc = _run(_env_with_shim(shim), "--repo-root", REPO_ROOT)
    if proc.returncode == 0:
        fail("update-fail: --update failure should fail the smoke")
    elif "update" not in proc.stderr.lower():
        fail(f"update-fail: stderr should name 'update'; got {proc.stderr!r}")
    else:
        ok("update-fail: --update closure failure fails the smoke")


# ---------------------------------------------------------------------------
# SKIP (exit 0) when install.py cannot be found — resilient self-build skip.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_INSTALL_PY"] = os.path.join(td, "nonexistent.py")
    proc = _run(env, "--repo-root", REPO_ROOT)
    if proc.returncode != 0:
        fail(f"skip-missing: missing install.py should SKIP (exit 0); "
             f"got {proc.returncode}; stderr={proc.stderr!r}")
    elif "skip" not in proc.stderr.lower():
        fail(f"skip-missing: stderr should note 'skipped'; got {proc.stderr!r}")
    else:
        ok("skip-missing: missing install.py skips gracefully (exit 0)")


sys.exit(FAIL)
