#!/usr/bin/env python3
"""test-sync-tree.py — e2e tests for scripts/sync-tree.py (Inv 38 / issue #524).

Inv 38 introduces a deterministic tick-start working-tree self-sync so the
loop runs the LATEST merged scripts instead of stale ones. The sync:

  1. Verifies the working tree is clean of uncommitted TRACKED changes (the
     same condition as safety-check.py Inv 5 — `git diff --quiet` AND
     `git diff --cached --quiet`; untracked files ignored). A dirty tree
     exits non-zero WITHOUT pulling.
  2. Runs `git pull --ff-only origin dev`. A non-fast-forwardable divergence
     fails loudly (exit non-zero); the script NEVER falls back to git merge.
  3. On success emits a result line and logs the outcome via tick-log.py.

These tests build a real local git fixture (a bare `origin` remote + a local
clone) and drive sync-tree.py through each scenario. To prove the script
NEVER invokes `git merge`, the tests inject a `git` SHIM via the
RABBIT_GIT_CMD env seam: the shim appends its full argv to a call-log file
then exec's the real git. After each run the tests assert no logged call
begins with `merge`.

Scenarios:
  A) Clean tree behind origin/dev → fast-forwards via `git pull --ff-only
     origin dev`, exits 0, status "synced"; `git merge` NEVER logged.
  B) Already up-to-date clean tree → exits 0 (noop-or-synced), no merge.
  C) Dirty tracked-file tree → exits non-zero, NO pull happened (origin sha
     unchanged in local HEAD), `git merge` NEVER logged.
  D) Divergent (non-ff) local history → exits non-zero loudly, `git merge`
     NEVER logged.
"""

import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
SYNC = os.path.join(SCRIPTS, "sync-tree.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def git(cwd, *args, check=True):
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {proc.stderr}"
        )
    return proc


def write_git_shim(dirpath, call_log):
    """Write a `git` shim that records argv to call_log then exec's real git.

    Returns the absolute path to the shim, to be passed via RABBIT_GIT_CMD.
    """
    real_git = subprocess.run(
        ["which", "git"], capture_output=True, text=True
    ).stdout.strip()
    shim = os.path.join(dirpath, "git")
    with open(shim, "w") as f:
        f.write(f"""#!/usr/bin/env python3
import os, sys
with open({call_log!r}, "a") as _t:
    _t.write(" ".join(sys.argv[1:]) + "\\n")
os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])
""")
    st = os.stat(shim)
    os.chmod(shim, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


def read_calls(call_log):
    if not os.path.isfile(call_log):
        return []
    with open(call_log) as f:
        return [ln.strip() for ln in f if ln.strip()]


def merge_invoked(call_log):
    """True iff any recorded git invocation's first token is 'merge'."""
    for line in read_calls(call_log):
        toks = line.split()
        if toks and toks[0] == "merge":
            return True
    return False


def make_fixture(root):
    """Build a bare `origin` with a `dev` branch + a local clone tracking it.

    Returns (origin_dir, clone_dir).
    """
    origin = os.path.join(root, "origin.git")
    seed = os.path.join(root, "seed")
    clone = os.path.join(root, "clone")
    os.makedirs(origin)
    os.makedirs(seed)

    git(origin, "init", "--bare", "-b", "dev")

    # Seed the dev branch with an initial commit.
    git(seed, "init", "-b", "dev")
    git(seed, "config", "user.email", "t@t")
    git(seed, "config", "user.name", "t")
    with open(os.path.join(seed, "tracked.txt"), "w") as f:
        f.write("v1\n")
    git(seed, "add", "tracked.txt")
    git(seed, "commit", "-m", "seed")
    git(seed, "remote", "add", "origin", origin)
    git(seed, "push", "origin", "dev")

    # Clone for the loop's working tree.
    git(root, "clone", origin, "clone")
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    git(clone, "checkout", "dev")
    return origin, seed, clone


def advance_origin(seed, content):
    """Add one more commit to origin/dev via the seed clone."""
    with open(os.path.join(seed, "tracked.txt"), "w") as f:
        f.write(content)
    git(seed, "add", "tracked.txt")
    git(seed, "commit", "-m", "advance")
    git(seed, "push", "origin", "dev")


def run_sync(clone, git_shim, call_log):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = clone
    env["RABBIT_GIT_CMD"] = git_shim
    # Keep tick-log writes inside the tmpdir.
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(clone, ".rabbit")
    return subprocess.run(
        [sys.executable, SYNC],
        cwd=clone, capture_output=True, text=True, env=env,
    )


# ---------------------------------------------------------------------------
# Scenario A — clean tree behind origin/dev fast-forwards, exit 0, no merge
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    origin, seed, clone = make_fixture(d)
    advance_origin(seed, "v2\n")  # origin/dev now ahead of the clone
    call_log = os.path.join(d, "calls-A.txt")
    shim = write_git_shim(d, call_log)

    before = git(clone, "rev-parse", "HEAD").stdout.strip()
    proc = run_sync(clone, shim, call_log)
    after = git(clone, "rev-parse", "HEAD").stdout.strip()

    if proc.returncode != 0:
        fail(f"A: clean-behind sync exit {proc.returncode}; "
             f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    else:
        ok("A: clean tree behind origin fast-forwards (exit 0)")
    if after == before:
        fail("A: HEAD did not advance — fast-forward did not happen")
    else:
        ok("A: HEAD advanced to origin/dev (fast-forward applied)")
    if merge_invoked(call_log):
        fail(f"A: git merge WAS invoked; calls={read_calls(call_log)!r}")
    else:
        ok("A: git merge NEVER invoked (used git pull --ff-only)")
    # A `git pull` MUST have been used (the binding mechanism).
    if any(c.split()[0:1] == ["pull"] for c in read_calls(call_log)):
        ok("A: git pull was the sync mechanism")
    else:
        fail(f"A: git pull was not invoked; calls={read_calls(call_log)!r}")


# ---------------------------------------------------------------------------
# Scenario B — already up to date: clean exit 0, no merge
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    origin, seed, clone = make_fixture(d)
    call_log = os.path.join(d, "calls-B.txt")
    shim = write_git_shim(d, call_log)

    proc = run_sync(clone, shim, call_log)
    if proc.returncode != 0:
        fail(f"B: up-to-date sync exit {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("B: already-up-to-date clean tree exits 0")
    if merge_invoked(call_log):
        fail(f"B: git merge WAS invoked; calls={read_calls(call_log)!r}")
    else:
        ok("B: git merge NEVER invoked on an up-to-date tree")


# ---------------------------------------------------------------------------
# Scenario C — dirty tracked file: exit non-zero, NO pull, no merge
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    origin, seed, clone = make_fixture(d)
    advance_origin(seed, "v2\n")  # origin is ahead so a pull WOULD ff if run
    # Dirty a TRACKED file in the clone (unstaged modification).
    with open(os.path.join(clone, "tracked.txt"), "a") as f:
        f.write("local edit\n")
    call_log = os.path.join(d, "calls-C.txt")
    shim = write_git_shim(d, call_log)

    before = git(clone, "rev-parse", "HEAD").stdout.strip()
    proc = run_sync(clone, shim, call_log)
    after = git(clone, "rev-parse", "HEAD").stdout.strip()

    if proc.returncode == 0:
        fail("C: dirty tracked tree exited 0 (must fail loudly)")
    else:
        ok("C: dirty tracked-file tree exits non-zero")
    if after != before:
        fail("C: HEAD advanced despite dirty tree — pull should NOT have run")
    else:
        ok("C: no pull happened (HEAD unchanged on dirty tree)")
    # A `git pull` must NOT have been invoked on a dirty tree.
    if any(c.split()[0:1] == ["pull"] for c in read_calls(call_log)):
        fail(f"C: git pull ran on a dirty tree; calls={read_calls(call_log)!r}")
    else:
        ok("C: git pull NOT invoked on a dirty tree")
    if merge_invoked(call_log):
        fail(f"C: git merge WAS invoked; calls={read_calls(call_log)!r}")
    else:
        ok("C: git merge NEVER invoked on a dirty tree")


# ---------------------------------------------------------------------------
# Scenario D — divergent (non-ff) local history: exit non-zero loudly, no merge
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    origin, seed, clone = make_fixture(d)
    advance_origin(seed, "origin-side\n")  # origin/dev advances
    # Commit a DIFFERENT change locally so histories diverge (non-ff).
    with open(os.path.join(clone, "tracked.txt"), "w") as f:
        f.write("local-side\n")
    git(clone, "add", "tracked.txt")
    git(clone, "commit", "-m", "local divergent commit")
    call_log = os.path.join(d, "calls-D.txt")
    shim = write_git_shim(d, call_log)

    proc = run_sync(clone, shim, call_log)
    if proc.returncode == 0:
        fail("D: divergent non-ff tree exited 0 (must fail loudly)")
    else:
        ok("D: divergent non-ff history exits non-zero loudly")
    if merge_invoked(call_log):
        fail(f"D: git merge WAS invoked on divergence; "
             f"calls={read_calls(call_log)!r}")
    else:
        ok("D: git merge NEVER invoked on divergence (no force-merge fallback)")


# ---------------------------------------------------------------------------
# --help smoke
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SYNC, "--help"], capture_output=True, text=True
)
if proc.returncode != 0:
    fail(f"--help: sync-tree.py exit {proc.returncode}; stderr={proc.stderr!r}")
elif "sync" not in (proc.stdout + proc.stderr).lower():
    fail("--help: usage text missing 'sync'")
else:
    ok("--help: sync-tree.py exits 0 with recognizable usage")


sys.exit(FAIL)
