#!/usr/bin/env python3
"""test-install-closure-integrity.py — Inv 64.

Cross-feature install-closure-integrity gate. The rabbit-cage install closure
(`.claude/features/rabbit-cage/install.py`) enumerates a SOURCE path for every
feature surface it copies during `curl … install.sh | bash`; install.main()
aborts on a missing source, so a surface retirement that leaves a stale closure
entry silently breaks every fresh install. That closure spans ALL features, but
the install-integrity self-check only ran when rabbit-cage itself was touched —
so a surface change to a DIFFERENT feature could break install without any gate
running.

This test wires the closure-integrity check into contract's cross-feature gate
(the repo-wide gate that runs on every feature's PR). It imports rabbit-cage's
importable `check_install_sources_exist(repo_root)` and asserts it returns an
EMPTY list against the REAL repo root — i.e. every closure source exists on
disk. On a non-empty result it FAILS, naming the dangling source path(s).

  t1: every install.py closure source exists under the real repo root
      (check_install_sources_exist returns []).

Degenerate self-build: if rabbit-cage/install.py is legitimately absent (no
install closure to verify), the check is SKIPPED gracefully rather than
errored. In the normal repo install.py is present and the check MUST run.
"""

import os
import sys
import subprocess
import importlib.util

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)


def repo_root():
    result = subprocess.run(
        ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    # Fallback: repo root is four levels up from this test file
    # (<root>/.claude/features/contract/test/<this>).
    return os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))


ROOT = repo_root()
INSTALL_PY = os.path.join(ROOT, ".claude/features/rabbit-cage/install.py")

FAIL = 0


def fail_t(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"PASS t{n}: {msg}")


# Degenerate self-build: no install closure to verify -> skip gracefully.
if not os.path.isfile(INSTALL_PY):
    print(
        "SKIP t1: rabbit-cage/install.py absent (degenerate self-build); "
        "no install closure to verify"
    )
    print("\nResults: skipped (no install.py)")
    sys.exit(0)

spec = importlib.util.spec_from_file_location("rabbit_cage_install_closure", INSTALL_PY)
install_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install_mod)

check = getattr(install_mod, "check_install_sources_exist", None)
if check is None:
    fail_t(1, "rabbit-cage/install.py does not export check_install_sources_exist")
else:
    missing = check(ROOT)
    if missing:
        fail_t(
            1,
            "install.py closure references source path(s) absent on disk — "
            "fresh install would abort: " + ", ".join(missing),
        )
    else:
        ok(1, "all install.py closure sources exist on disk")

print()
print(f"Results: {'1 passed' if FAIL == 0 else '1 failed'}")
sys.exit(0 if FAIL == 0 else 1)
