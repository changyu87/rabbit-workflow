#!/usr/bin/env python3
"""test-gitignore-seeded-runtime-artifacts.py — spec Inv 52 (issue #398).

Inv 52 makes proactive `.gitignore` seeding the policy: the repo-root
`.gitignore` MUST be seeded up front with the full known set of runtime
artifacts the Claude Code platform and the rabbit workflow write into a
checkout, so a newly-running loop or subagent never trips
`safety-check.py` Invariant 5 ("working tree clean") on an artifact
discovered the hard way.

The genuinely-missing pattern this test guards is the per-feature
scope-marker glob `.rabbit-scope-active-*`: the bare `.rabbit-scope-active`
token (an exact match) does NOT cover a per-feature
`.rabbit-scope-active-<feature>` marker, so without the glob a stray
per-feature marker (e.g. `.rabbit-scope-active-rabbit-cage`) can be
committed.

Test method: copy the repo-root `.gitignore` into a fresh tempdir, run
`git init -q`, write each artifact in the known seed set — including a
concrete per-feature marker `.rabbit-scope-active-rabbit-cage` — run
`git status --porcelain --untracked-files=all`, and assert none of them
appear in the output. Fails loudly naming any artifact that shows as `??`.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when the Claude Code platform and rabbit features
expose a single declarative manifest of runtime-artifact paths that
`.gitignore` can be generated from, superseding the hand-seeded list, or
when rabbit-auto-evolve is retired.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
GITIGNORE = REPO_ROOT / ".gitignore"

# The known seed set: a representative artifact from each runtime-artifact
# class Inv 52 requires the repo-root .gitignore to cover. The per-feature
# scope marker .rabbit-scope-active-rabbit-cage is the case the bare
# .rabbit-scope-active token misses — the reason Inv 52 mandates the glob.
SEED_ARTIFACTS = [
    ".rabbit-scope-active-rabbit-cage",
    ".rabbit-auto-evolve-active",
    ".claude/scheduled_tasks.lock",
    ".claude/scheduled_tasks.json",
    ".rabbit-scope-override",
    ".rabbit-human-approval-bypass",
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


print("test-gitignore-seeded-runtime-artifacts.py")

# --- t1: repo-root .gitignore exists ---
if GITIGNORE.is_file():
    ok("exists", str(GITIGNORE))
else:
    fail_t("exists", f"repo-root .gitignore not found: {GITIGNORE}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# --- t2: every seeded artifact is ignored by `git status --porcelain` ---
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
        for rel in SEED_ARTIFACTS:
            fp = td / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("session")

        # --untracked-files=all forces git to list each untracked file
        # individually rather than collapsing to its parent directory;
        # without this `.claude/` would show up as a single `?? .claude/`
        # line that substring-matches neither nested filename, producing a
        # false pass when those gitignore entries are missing.
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
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
            leaked = [a for a in SEED_ARTIFACTS if a in status.stdout]
            if leaked:
                fail_t(
                    "ignored",
                    f"these seeded runtime artifacts appear in "
                    f"`git status --porcelain` output: {leaked!r}; "
                    f"full stdout={status.stdout!r}",
                )
            else:
                ok(
                    "ignored",
                    "none of the seeded runtime artifacts appear in "
                    "git status",
                )

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
