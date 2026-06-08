#!/usr/bin/env python3
"""test-check-release-update-runtime-root.py — contract Inv 53 / #1065.

Regression guard for the vendored-mode `.rabbit/.rabbit/.runtime/last-update-check`
doubling.

In a vendored install the session exports `RABBIT_ROOT=<host>/.rabbit`.
scripts/check-release-update.py resolved its `ts_path` by unconditionally joining
`<repo_root>/.rabbit/.runtime/last-update-check`. With `repo_root` already the
`.rabbit` dir that DOUBLES to `<host>/.rabbit/.rabbit/.runtime/last-update-check`,
diverging from where SessionStart / scope-guard read the throttle file.

check-release-update.py MUST anchor `last-update-check` at the canonical single-
`.rabbit` runtime root via rabbit-cage's `rabbit_runtime_root` resolver (Inv 52):
`<rabbit_runtime_root(repo_root)>/.runtime/last-update-check`.

This test:
  - VENDORED: RABBIT_ROOT basename is `.rabbit`; after a forced fetch attempt the
    throttle file MUST land at `<rabbit_root>/.runtime/last-update-check` (single),
    NOT the doubled `<rabbit_root>/.rabbit/.runtime/...`.
  - STANDALONE: RABBIT_ROOT basename is NOT `.rabbit`; throttle file MUST land at
    `<root>/.rabbit/.runtime/last-update-check` (unchanged behavior).

The real runtime_root.py resolver is copied into the simulated vendored/standalone
layout so the script exercises the canonical resolver, not a stub.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes a native release-channel update
    notification mechanism that supersedes this helper.
"""
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_SCRIPT = os.path.join(FEATURE_DIR, "scripts", "check-release-update.py")
WORKSPACE_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
REAL_RESOLVER = os.path.join(
    WORKSPACE_ROOT, ".claude", "features", "rabbit-cage", "lib", "runtime_root.py"
)

# urlopen shim that raises so the fetch fails: silent exit 0, but the throttle
# file IS written after the attempt (the path we assert on).
SHIM_SRC = """
import urllib.request, urllib.error
def _fake(req, timeout=None):
    raise urllib.error.URLError("network-down")
urllib.request.urlopen = _fake
"""


def install_layout(root):
    """Copy the real check-release-update.py + rabbit-cage runtime_root.py
    resolver into a `.claude/features/...` tree under `root`, returning the path
    to the installed script."""
    contract_scripts = os.path.join(
        root, ".claude", "features", "contract", "scripts")
    cage_lib = os.path.join(
        root, ".claude", "features", "rabbit-cage", "lib")
    os.makedirs(contract_scripts, exist_ok=True)
    os.makedirs(cage_lib, exist_ok=True)

    target = os.path.join(contract_scripts, "check-release-update.py")
    shutil.copy(REAL_SCRIPT, target)
    os.chmod(target, 0o755)
    shutil.copy(REAL_RESOLVER, os.path.join(cage_lib, "runtime_root.py"))
    return target


def run(target, repo_root):
    with tempfile.TemporaryDirectory() as shim_dir:
        with open(os.path.join(shim_dir, "sitecustomize.py"), "w") as f:
            f.write(SHIM_SRC)
        env = os.environ.copy()
        env["RABBIT_ROOT"] = repo_root
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = shim_dir + (os.pathsep + existing if existing else "")
        return subprocess.run(
            [sys.executable, target],
            capture_output=True, text=True, timeout=30, env=env,
        )


def main():
    fail = 0

    if not os.path.isfile(REAL_RESOLVER):
        print(f"FAIL: precondition — resolver missing: {REAL_RESOLVER}",
              file=sys.stderr)
        return 1

    # --- VENDORED: RABBIT_ROOT basename IS .rabbit -------------------------
    with tempfile.TemporaryDirectory() as host:
        rabbit_root = os.path.join(host, ".rabbit")
        target = install_layout(rabbit_root)
        with open(os.path.join(rabbit_root, ".version"), "w") as f:
            f.write("dev")
        r = run(target, rabbit_root)
        if r.returncode != 0:
            print(f"FAIL[vendored]: expected exit 0, got {r.returncode}; "
                  f"stderr={r.stderr!r}", file=sys.stderr)
            fail = 1

        single = os.path.join(rabbit_root, ".runtime", "last-update-check")
        doubled = os.path.join(rabbit_root, ".rabbit", ".runtime",
                               "last-update-check")
        if os.path.isfile(doubled):
            print(f"FAIL[vendored]: throttle file DOUBLED at {doubled!r} "
                  f"(must be single at {single!r})", file=sys.stderr)
            fail = 1
        elif not os.path.isfile(single):
            print(f"FAIL[vendored]: throttle file not at canonical single path "
                  f"{single!r}", file=sys.stderr)
            fail = 1
        else:
            print("PASS: vendored throttle file lands at single-.rabbit path")

    # --- STANDALONE: RABBIT_ROOT basename is NOT .rabbit -------------------
    with tempfile.TemporaryDirectory() as host:
        target = install_layout(host)
        with open(os.path.join(host, ".version"), "w") as f:
            f.write("dev")
        r = run(target, host)
        if r.returncode != 0:
            print(f"FAIL[standalone]: expected exit 0, got {r.returncode}; "
                  f"stderr={r.stderr!r}", file=sys.stderr)
            fail = 1

        expected = os.path.join(host, ".rabbit", ".runtime",
                                "last-update-check")
        if not os.path.isfile(expected):
            print(f"FAIL[standalone]: throttle file not at expected path "
                  f"{expected!r}", file=sys.stderr)
            fail = 1
        else:
            print("PASS: standalone throttle file lands at <root>/.rabbit path")

    if fail:
        print("test-check-release-update-runtime-root: FAIL", file=sys.stderr)
        return 1
    print("test-check-release-update-runtime-root: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
