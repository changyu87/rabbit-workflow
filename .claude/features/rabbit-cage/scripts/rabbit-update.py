#!/usr/bin/env python3
"""rabbit-update.py — backs the /rabbit-update slash command (spec Inv 35).

Two deterministic subcommands:

  check    Non-mutating current-vs-latest release probe. Prints a single JSON
           line: {"current", "latest", "newer", "self_update_available"}.
           Reuses contract's check-release-update.py fetch/compare helpers
           (read_version / fetch_upstream_version / resolve_repo_root /
           probe_self_update) rather than duplicating the urllib fetch or the
           version compare. Unlike the SessionStart check_release_update path,
           this probe is NOT throttled and writes NO throttle file — an
           explicit user request always forces a fresh probe. For deterministic
           testing the latest tag may be injected via RABBIT_UPDATE_TEST_LATEST,
           bypassing the network fetch.

  install  Applies the self-update by invoking the existing install.py
           self-update path: <rabbit_root>/install.py --update (the SOLE update
           mechanism per spec Inv 22). No fetch/copy logic is re-implemented
           here; install.py owns the in-place refresh.

repo_root resolves from RABBIT_ROOT (plugin mode) when set, otherwise from
`git rev-parse --show-toplevel`, mirroring the other rabbit-cage scripts.

Usage:
  rabbit-update.py check
  rabbit-update.py install

Exit: 0 success, 1 error, 2 bad invocation.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the rabbit CLI exposes a native self-update
    command that subsumes /rabbit-update.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "changyu87/rabbit-workflow"


def usage() -> None:
    sys.stderr.write(
        "usage:\n"
        "  rabbit-update.py check\n"
        "  rabbit-update.py install\n"
    )


def repo_root() -> Path:
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return Path(env)
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip())
    except Exception:
        # scripts/rabbit-update.py -> parents: [0]=scripts [1]=rabbit-cage
        # [2]=features [3]=.claude [4]=repo_root
        return Path(__file__).resolve().parents[4]


def _load_check_release(rroot: Path):
    """Import the contract-owned release-check helpers (Inv 35 reuse)."""
    path = rroot / ".claude/features/contract/scripts/check-release-update.py"
    spec = importlib.util.spec_from_file_location(
        "rabbit_check_release_update", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load check-release-update.py from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cmd_check(rroot: Path) -> int:
    try:
        cru = _load_check_release(rroot)
    except (ImportError, OSError) as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1

    version_path = os.path.join(str(rroot), ".version")
    current = cru.read_version(version_path)
    if current is None or current == "":
        sys.stderr.write(
            f"ERROR: cannot read installed version at {version_path}\n")
        return 1

    # Non-throttled, explicit probe: a test injection bypasses the network.
    injected = os.environ.get("RABBIT_UPDATE_TEST_LATEST")
    if injected is not None:
        latest = injected.strip()
    else:
        repo = os.environ.get("RABBIT_REPO", DEFAULT_REPO)
        latest = cru.fetch_upstream_version(repo, current)

    if latest is None or latest == "":
        sys.stderr.write(
            "ERROR: could not determine latest release (network failure?)\n")
        return 1

    self_update = cru.probe_self_update(str(rroot))
    sys.stdout.write(json.dumps({
        "current": current,
        "latest": latest,
        "newer": latest != current,
        "self_update_available": self_update,
    }) + "\n")
    return 0


def cmd_install(rroot: Path) -> int:
    install_py = rroot / "install.py"
    if not install_py.is_file():
        sys.stderr.write(f"ERROR: install.py not found at {install_py}\n")
        return 1
    return subprocess.call([sys.executable, str(install_py), "--update"])


def main() -> int:
    args = sys.argv[1:]
    if not args:
        usage()
        return 2
    cmd = args[0]
    rroot = repo_root()

    if cmd == "check":
        return cmd_check(rroot)
    if cmd == "install":
        return cmd_install(rroot)
    if cmd in ("-h", "--help", "help"):
        usage()
        return 0

    sys.stderr.write(f"ERROR: unknown subcommand '{cmd}'\n")
    usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
