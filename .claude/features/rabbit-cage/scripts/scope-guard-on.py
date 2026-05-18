#!/usr/bin/env python3
"""scope-guard-on.py — Revoke the scope-guard override, re-arming default-deny.

Removes .rabbit-scope-override (if present) so scope-guard.py returns to its
default-deny posture. Canonical answer to "scope guard back on" /
"revoke the session override".

Usage:
  .claude/features/rabbit-cage/scripts/scope-guard-on.py

Behaviour:
  - If .rabbit-scope-override exists: deletes it and prints a confirmation.
  - If .rabbit-scope-override is absent: no-op, exits 0.
"""

import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    # BUG-58: prefer git rev-parse from the script location; do not fall back
    # to a hard-coded .parent.parent.parent.parent chain because that
    # silently produces the wrong directory if the script ever moves or is
    # symlinked. If git is unavailable, fail loudly instead of guessing.
    env = os.environ.get("RABBIT_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    try:
        out = subprocess.check_output(
            ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip())
    except Exception:
        sys.stderr.write(
            "scope-guard-on.py: cannot determine repo root "
            "(set RABBIT_ROOT or run inside a git working tree)\n"
        )
        sys.exit(2)


def main() -> int:
    override_file = repo_root() / ".rabbit-scope-override"
    if override_file.is_file():
        override_file.unlink()
        print("[rabbit] Scope guard re-armed — .rabbit-scope-override removed.")
    else:
        print("[rabbit] Scope guard is already on — no active override to revoke.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
