#!/usr/bin/env python3
"""validate-all.py — sweep validate-feature.py across every feature directory
under a given root.

Usage:
  validate-all.py [<features-root>] [--validator <path>]

Default <features-root> is $FEATURES_ROOT, then ".claude/features".
Default --validator is autodetected (well-known relative paths).

Exit:
  0 all features pass (or no features found)
  1 one or more features fail
  2 validator not found / invocation error
"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root_arg = ""
    validator = ""
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--validator" and i + 1 < len(args):
            validator = args[i + 1]; i += 2
        elif a in ("-h", "--help"):
            sys.stderr.write(
                "usage: validate-all.py [<features-root>] [--validator <path>]\n"
            )
            return 0
        elif a.startswith("-"):
            sys.stderr.write(f"unknown arg: {a}\n")
            return 2
        else:
            root_arg = a; i += 1

    root = root_arg or os.environ.get("FEATURES_ROOT", ".claude/features")

    if not validator:
        script_dir = Path(__file__).resolve().parent
        repo_root = os.environ.get("RABBIT_ROOT")
        if not repo_root:
            try:
                repo_root = subprocess.check_output(
                    ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
            except Exception:
                repo_root = ""
        candidates = []
        if repo_root:
            candidates.append(Path(repo_root) / ".claude/features/contract/scripts/validate-feature.py")
        candidates.append(Path(".claude/features/contract/scripts/validate-feature.py"))
        for c in candidates:
            if c.is_file() and os.access(str(c), os.X_OK):
                validator = str(c); break

    if not validator or not Path(validator).is_file():
        sys.stderr.write(
            "ERROR: validate-feature.py not found "
            "(set --validator <path> or install contract scripts)\n"
        )
        return 2

    root_path = Path(root)
    if not root_path.is_dir():
        print(f"OK: features root '{root}' does not exist (vacuous pass)")
        return 0

    features = []
    for d in sorted(root_path.iterdir()):
        if not d.is_dir():
            continue
        if (d / "feature.json").is_file():
            features.append(d)

    if not features:
        print(f"OK: no features found under '{root}' (vacuous pass)")
        return 0

    passed = 0
    failed = 0
    failed_names = []
    for d in features:
        name = d.name
        rc = subprocess.call(
            [sys.executable, validator, str(d)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if rc == 0:
            print(f"  PASS: {name}"); passed += 1
        else:
            print(f"  FAIL: {name}"); failed += 1; failed_names.append(name)

    print()
    print(f"summary: {passed} passed, {failed} failed (root: {root})")
    if failed:
        sys.stderr.write(f"failed features: {' '.join(failed_names)}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
