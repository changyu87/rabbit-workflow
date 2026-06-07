#!/usr/bin/env python3
"""test-sync-tree.py — e2e tests for scripts/sync-tree.py (Inv 38 / issue #524).

Inv 38 introduces a deterministic tick-start working-tree self-sync so the
loop runs the LATEST merged scripts instead of stale ones. The sync:

  1. Verifies the working tree is clean of uncommitted TRACKED changes (the
     same condition as safety-check.py Inv 5 — `git diff --quiet` AND
     `git diff --cached --quiet`; untracked files ignored). A dirty tree
     exits non-zero WITHOUT pulling.
  2. Runs `git pull --ff-only origin <integration-target>` (Inv 61: default
     main). A non-fast-forwardable divergence fails loudly (exit non-zero);
     the script NEVER falls back to git merge.
  3. On success emits a result line and logs the outcome via tick-log.py.

These tests build a real local git fixture (a bare `origin` remote + a local
clone) and drive sync-tree.py through each scenario. To prove the script
NEVER invokes `git merge`, the tests inject a `git` SHIM via the
RABBIT_GIT_CMD env seam: the shim appends its full argv to a call-log file
then exec's the real git. After each run the tests assert no logged call
begins with `merge`.

Scenarios:
  A) Clean tree behind origin/main → fast-forwards via `git pull --ff-only
     origin main`, exits 0, status "synced"; `git merge` NEVER logged.
  B) Already up-to-date clean tree → exits 0 (noop-or-synced), no merge.
  C) Dirty tracked-file tree → exits non-zero, NO pull happened (origin sha
     unchanged in local HEAD), `git merge` NEVER logged.
  D) Divergent (non-ff) local history → exits non-zero loudly, `git merge`
     NEVER logged.
  E) Target=dev (override; still accepted during coexistence teardown) → the
     pull source is resolved from the integration target, so the shim call-log
     shows `pull --ff-only origin dev` (issue #1006 / Inv 61).
  F) Target=main (RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET=main) → the pull
     source resolves to main, so the shim call-log shows `pull --ff-only
     origin main` and the clone fast-forwards to origin/main (issue #1006 /
     Inv 61).
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


def make_fixture(root, branch="main"):
    """Build a bare `origin` with `branch` + a local clone tracking it.

    Returns (origin_dir, seed_dir, clone_dir).
    """
    origin = os.path.join(root, "origin.git")
    seed = os.path.join(root, "seed")
    clone = os.path.join(root, "clone")
    os.makedirs(origin)
    os.makedirs(seed)

    git(origin, "init", "--bare", "-b", branch)

    # Seed the integration branch with an initial commit.
    git(seed, "init", "-b", branch)
    git(seed, "config", "user.email", "t@t")
    git(seed, "config", "user.name", "t")
    with open(os.path.join(seed, "tracked.txt"), "w") as f:
        f.write("v1\n")
    git(seed, "add", "tracked.txt")
    git(seed, "commit", "-m", "seed")
    git(seed, "remote", "add", "origin", origin)
    git(seed, "push", "origin", branch)

    # Clone for the loop's working tree.
    git(root, "clone", origin, "clone")
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    git(clone, "checkout", branch)
    return origin, seed, clone


def advance_origin(seed, content, branch="main"):
    """Add one more commit to origin/<branch> via the seed clone."""
    with open(os.path.join(seed, "tracked.txt"), "w") as f:
        f.write(content)
    git(seed, "add", "tracked.txt")
    git(seed, "commit", "-m", "advance")
    git(seed, "push", "origin", branch)


def run_sync(clone, git_shim, call_log, target=None):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = clone
    env["RABBIT_GIT_CMD"] = git_shim
    # Keep tick-log writes inside the tmpdir.
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(clone, ".rabbit")
    # Resolve the pull source from the integration target (Inv 61). When
    # target is None the env var is cleared so the default (main) applies.
    if target is not None:
        env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = target
    else:
        env.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
    return subprocess.run(
        [sys.executable, SYNC],
        cwd=clone, capture_output=True, text=True, env=env,
    )


# ---------------------------------------------------------------------------
# Scenario A — clean tree behind origin/main fast-forwards, exit 0, no merge
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    origin, seed, clone = make_fixture(d)
    advance_origin(seed, "v2\n")  # origin/main now ahead of the clone
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
        ok("A: HEAD advanced to origin/main (fast-forward applied)")
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
    advance_origin(seed, "origin-side\n")  # origin/main advances
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


def pull_source(call_log):
    """Return the `origin <branch>` source of the recorded `pull --ff-only`
    invocation, or None if no such call was logged."""
    for line in read_calls(call_log):
        toks = line.split()
        if toks[:2] == ["pull", "--ff-only"]:
            return " ".join(toks[2:])
    return None


# ---------------------------------------------------------------------------
# Scenario E — target=dev (override) resolves the pull source to `origin dev`
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    origin, seed, clone = make_fixture(d, branch="dev")
    advance_origin(seed, "v2\n", branch="dev")
    call_log = os.path.join(d, "calls-E.txt")
    shim = write_git_shim(d, call_log)

    proc = run_sync(clone, shim, call_log, target="dev")
    if proc.returncode != 0:
        fail(f"E: target=dev sync exit {proc.returncode}; "
             f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    else:
        ok("E: target=dev clean tree fast-forwards (exit 0)")
    src = pull_source(call_log)
    if src == "origin dev":
        ok("E: pull source resolved to `origin dev` for target=dev")
    else:
        fail(f"E: expected `pull --ff-only origin dev`; got source {src!r}; "
             f"calls={read_calls(call_log)!r}")


# ---------------------------------------------------------------------------
# Scenario F — target=main resolves the pull source to `origin main`
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    origin, seed, clone = make_fixture(d, branch="main")
    advance_origin(seed, "v2\n", branch="main")
    call_log = os.path.join(d, "calls-F.txt")
    shim = write_git_shim(d, call_log)

    before = git(clone, "rev-parse", "HEAD").stdout.strip()
    proc = run_sync(clone, shim, call_log, target="main")
    after = git(clone, "rev-parse", "HEAD").stdout.strip()

    if proc.returncode != 0:
        fail(f"F: target=main sync exit {proc.returncode}; "
             f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    else:
        ok("F: target=main clean tree fast-forwards (exit 0)")
    src = pull_source(call_log)
    if src == "origin main":
        ok("F: pull source resolved to `origin main` for target=main")
    else:
        fail(f"F: expected `pull --ff-only origin main`; got source {src!r}; "
             f"calls={read_calls(call_log)!r}")
    if after == before:
        fail("F: HEAD did not advance — fast-forward to origin/main did not happen")
    else:
        ok("F: HEAD advanced to origin/main (fast-forward applied)")
    if merge_invoked(call_log):
        fail(f"F: git merge WAS invoked; calls={read_calls(call_log)!r}")
    else:
        ok("F: git merge NEVER invoked (used git pull --ff-only)")


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
