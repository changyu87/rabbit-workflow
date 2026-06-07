#!/usr/bin/env python3
"""test-markers-gitignored.py — spec Inv 23 (added v0.8.0 for issue #389).

Asserts the repo-root `.gitignore` carries a glob that covers all five
rabbit-auto-evolve runtime markers:

  .rabbit-auto-evolve-active
  .rabbit-auto-evolve-running
  .rabbit-auto-evolve-stop-requested
  .rabbit-auto-evolve-restart-needed
  .rabbit-auto-evolve-aborted

Without this gitignore entry, `safety-check.py` Invariant 5 ("working tree
clean") fails during the `merge` phase whenever the loop is running — the
active and running markers show as `??` untracked files and every PR merge
is refused, deadlocking the loop indefinitely.

Test method: copy the repo-root `.gitignore` into a fresh tempdir, run
`git init -q`, touch all five marker files, run `git status --porcelain`,
and assert none of the five marker basenames appear in the output.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when rabbit-auto-evolve is retired or when the
runtime markers are relocated under an already-gitignored prefix
(e.g. `.rabbit/`).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
GITIGNORE = REPO_ROOT / ".gitignore"

MARKERS = [
    ".rabbit-auto-evolve-active",
    ".rabbit-auto-evolve-running",
    ".rabbit-auto-evolve-stop-requested",
    ".rabbit-auto-evolve-restart-needed",
    ".rabbit-auto-evolve-aborted",
    ".rabbit-auto-evolve-restart-advised",
]


pass_n = 0
fail_n = 0


def ok(t: str, msg: str) -> None:
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t: str, msg: str) -> None:
    global fail_n
    print(f"  FAIL {t}: {msg}")
    fail_n += 1


print("test-markers-gitignored.py")

# --- t1: repo-root .gitignore exists ---
if GITIGNORE.is_file():
    ok("exists", str(GITIGNORE))
else:
    fail_t("exists", f"repo-root .gitignore not found: {GITIGNORE}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# --- t2: all five markers are ignored by `git status --porcelain` ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    shutil.copy(GITIGNORE, td / ".gitignore")

    init = subprocess.run(
        ["git", "init", "-q"],
        cwd=td,
        capture_output=True,
        text=True,
    )
    if init.returncode != 0:
        fail_t(
            "git-init",
            f"exit {init.returncode}; stderr={init.stderr!r}",
        )
    else:
        for name in MARKERS:
            (td / name).write_text("session")

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=td,
            capture_output=True,
            text=True,
        )
        if status.returncode != 0:
            fail_t(
                "git-status",
                f"exit {status.returncode}; stderr={status.stderr!r}",
            )
        else:
            leaked = [m for m in MARKERS if m in status.stdout]
            if leaked:
                fail_t(
                    "ignored",
                    f"these markers appear in `git status --porcelain` "
                    f"output: {leaked!r}; full stdout={status.stdout!r}",
                )
            else:
                ok("ignored", "none of the five markers appear in git status")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
