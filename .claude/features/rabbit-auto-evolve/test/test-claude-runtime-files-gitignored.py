#!/usr/bin/env python3
"""test-claude-runtime-files-gitignored.py — spec Inv 24 (added v0.8.1).

Asserts the repo-root `.gitignore` carries entries that exclude the two
Claude Code scheduling-harness runtime files from `git status`:

  .claude/scheduled_tasks.lock
  .claude/scheduled_tasks.json

Without these gitignore entries, both files appear as `??` untracked in
`git status` whenever Claude Code's scheduling harness is active
(`CronCreate` / `ScheduleWakeup`), causing `safety-check.py` Invariant 5
("working tree clean") to refuse every PR merge attempt while a Claude
Code session is running — the same merge-phase deadlock pattern that
Inv 23 addresses for the `.rabbit-auto-evolve-*` markers.

Test method: copy the repo-root `.gitignore` into a fresh tempdir, run
`git init -q`, create both files under `.claude/`, run
`git status --porcelain`, and assert neither filename appears in the
output.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code stops creating
`.claude/scheduled_tasks.{lock,json}` (e.g. moves scheduling state under
an already-gitignored prefix) or when rabbit-auto-evolve is retired.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
GITIGNORE = REPO_ROOT / ".gitignore"

FILES = [
    ".claude/scheduled_tasks.lock",
    ".claude/scheduled_tasks.json",
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


print("test-claude-runtime-files-gitignored.py")

# --- t1: repo-root .gitignore exists ---
if GITIGNORE.is_file():
    ok("exists", str(GITIGNORE))
else:
    fail_t("exists", f"repo-root .gitignore not found: {GITIGNORE}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# --- t2: both files are ignored by `git status --porcelain` ---
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
        for rel in FILES:
            fp = td / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("")

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
            leaked = [f for f in FILES if f in status.stdout]
            if leaked:
                fail_t(
                    "ignored",
                    f"these files appear in `git status --porcelain` "
                    f"output: {leaked!r}; full stdout={status.stdout!r}",
                )
            else:
                ok(
                    "ignored",
                    "neither scheduled_tasks file appears in git status",
                )

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
