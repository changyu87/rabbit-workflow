#!/usr/bin/env python3
"""rabbit-tdd-autonomous-config.py — backs the /rabbit-tdd-autonomous command.

THIN wrapper over contract.lib.config_dispatch.dispatch_config for rabbit-feature's
ONE owned configurable: tdd-autonomous, which gates the TDD feature-touch Step-4
human-approval cycle (consumers: tdd-subagent/dispatch-tdd-subagent.py + the
rabbit-feature-touch SKILL). Phase 3 of #733 relocates this configurable to its
owning feature (out of rabbit-cage); the per-feature config command delegates
validation + mutation + restart-prompt rendering to the shared helper so the
generic interpreter logic lives ONCE in contract.lib (script > prompt; no N
drifting copies).

Polarity (post-#336): `tdd-autonomous false` (DEFAULT) keeps the Step-4 gate
ACTIVE (no bypass marker); `tdd-autonomous true` writes the canonical bypass
marker .rabbit-tdd-autonomous so the cycle skips Step 4.

This script owns ONLY argv parsing and IO. It:
  1. resolves repo_root (RABBIT_ROOT env in plugin mode, else
     `git rev-parse --show-toplevel`),
  2. reads rabbit-feature's OWN feature.json configuration[],
  3. finds the tdd-autonomous entry whose `subcommand` matches argv[1],
  4. calls dispatch_config(cfg, value, repo_root=..., feature_dir=...),
  5. prints result["messages"] then result["restart_prompt"] (when present),
     and exits non-zero with result["error"] to stderr on failure.

It MUST NOT re-implement the values/actions interpreter, the validation rules,
or the restart-prompt framing.

Usage:
  rabbit-tdd-autonomous-config.py tdd-autonomous true|false

Exit: 0 success, 1 dispatch/mutation error, 2 bad invocation.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the rabbit CLI exposes a native per-feature
    configuration mechanism that subsumes /rabbit-tdd-autonomous.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# This script lives at .claude/features/rabbit-feature/scripts/; the
# rabbit-feature dir is its parent's parent.
FEATURE_DIR = Path(__file__).resolve().parents[1]


def usage() -> None:
    sys.stderr.write(
        "usage:\n"
        "  rabbit-tdd-autonomous-config.py tdd-autonomous true|false\n"
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
        # scripts/rabbit-tdd-autonomous-config.py -> parents:
        # [0]=scripts [1]=rabbit-feature [2]=features [3]=.claude [4]=repo_root
        return Path(__file__).resolve().parents[4]


def _load_configuration(rroot: Path):
    """Read rabbit-feature's OWN configuration[] from its feature.json."""
    fj = rroot / ".claude/features/rabbit-feature/feature.json"
    with open(fj) as f:
        data = json.load(f)
    return data.get("configuration") or []


def main() -> int:
    args = sys.argv[1:]
    if not args:
        usage()
        return 2
    if args[0] in ("-h", "--help", "help"):
        usage()
        return 0

    subcommand = args[0]
    rroot = repo_root()

    # Make contract.lib importable the same way the other config commands do.
    contract_dir = rroot / ".claude/features/contract"
    if str(contract_dir) not in sys.path:
        sys.path.insert(0, str(contract_dir))
    try:
        from lib.config_dispatch import dispatch_config  # noqa: PLC0415
    except ImportError as e:
        sys.stderr.write(
            f"rabbit-tdd-autonomous: cannot import contract.lib.config_dispatch: {e}\n")
        return 1

    configuration = _load_configuration(rroot)
    matches = [c for c in configuration if c.get("subcommand") == subcommand]
    if not matches:
        known = sorted({c.get("subcommand", "") for c in configuration
                        if c.get("command") == "rabbit-tdd-autonomous"})
        sys.stderr.write(
            f"rabbit-tdd-autonomous: unknown subcommand '{subcommand}'\n")
        sys.stderr.write(f"Known subcommands: {', '.join(known)}\n")
        return 2
    cfg = matches[0]

    if len(args) < 2:
        sys.stderr.write(
            f"rabbit-tdd-autonomous {subcommand}: requires a value (true|false)\n")
        return 2
    value = args[1]

    result = dispatch_config(
        cfg, value,
        repo_root=str(rroot),
        feature_dir=str(FEATURE_DIR),
    )

    for msg in result.get("messages") or []:
        print(msg)

    if not result.get("ok"):
        err = result.get("error")
        if err:
            sys.stderr.write(f"{err}\n")
        return 1

    restart = result.get("restart_prompt")
    if restart:
        print(restart)
    return 0


if __name__ == "__main__":
    sys.exit(main())
