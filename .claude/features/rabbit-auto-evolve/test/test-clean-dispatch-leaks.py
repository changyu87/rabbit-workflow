#!/usr/bin/env python3
"""test-clean-dispatch-leaks.py — e2e tests for scripts/clean-dispatch-leaks.py
(Inv 43 / issue #583): deterministic, defense-in-depth pre-merge cleanup of
KNOWN worktree-dispatch leak-class noise from the dispatcher's main tree,
which otherwise trips safety-check Inv 5 and makes merge-prs.py skip the batch.

The cleanup MUST:
  1. Remove untracked stray `.rabbit-scope-active-*` markers at the repo root.
  2. Restore (to HEAD) ONLY a `<feature>/feature.json` whose diff touches ONLY
     loop-bookkeeping keys (tdd_last_cycle_impl_commit, tdd_state, updated, ...).
  3. Fail LOUDLY (non-zero) on UNEXPECTED tracked dirt and NOT discard it.
  4. Be a no-op on a clean tree.

Fixtures use a real `git init -b main` in a tempdir. No live network.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "clean-dispatch-leaks.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args],
                          capture_output=True, text=True)


def _tracked_dirty(repo):
    """True iff a tracked file has staged/unstaged modifications (Inv 5 view)."""
    unstaged = _git(repo, "diff", "--quiet").returncode
    staged = _git(repo, "diff", "--cached", "--quiet").returncode
    return unstaged != 0 or staged != 0


def _head(repo):
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def _make_repo(tmp, target="main"):
    """A git repo on the integration `target` branch with a committed
    feature.json under a feature dir, wired to a bare `origin` remote with the
    target pushed (so branch-restore tests can tell pushed feature commits from
    un-pushed ones). The cleanup is integration-target-aware (Inv 44 / Inv 61):
    the `main`-default repo simulates the post-cutover workflow; a `target=dev`
    repo simulates the coexistence-teardown override."""
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    _git(repo, "init", "-b", target)
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    feat_dir = os.path.join(repo, ".claude", "features", "rabbit-auto-evolve")
    os.makedirs(feat_dir)
    fj = os.path.join(feat_dir, "feature.json")
    with open(fj, "w") as f:
        json.dump({
            "name": "rabbit-auto-evolve",
            "version": "0.32.0",
            "tdd_state": "test-green",
            "updated": "2026-06-01",
        }, f, indent=2)
        f.write("\n")
    docs_dir = os.path.join(feat_dir, "docs")
    os.makedirs(docs_dir)
    spec = os.path.join(docs_dir, "spec.md")
    with open(spec, "w") as f:
        f.write("# spec\n\noriginal line\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    bare = os.path.join(tmp, "origin.git")
    subprocess.run(["git", "init", "--bare", bare],
                   capture_output=True, text=True)
    _git(repo, "remote", "add", "origin", bare)
    _git(repo, "push", "-u", "origin", target)
    return repo, fj, spec


def _run(repo, target=None):
    """Run the cleanup. When `target` is given, set the integration-target env
    override so the cleanup resolves that branch as the restore destination."""
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(repo, ".rabbit")
    if target is not None:
        env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = target
    else:
        env.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
    return subprocess.run([sys.executable, SCRIPT], cwd=repo,
                          capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# A — bookkeeping-only feature.json leak + stray marker → cleaned to clean tree.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    # Simulate the tdd-step bookkeeping leak: only a bookkeeping key changes.
    with open(fj) as f:
        data = json.load(f)
    data["tdd_last_cycle_impl_commit"] = "deadbeef"
    data["tdd_state"] = "impl"
    data["updated"] = "2026-06-03"
    with open(fj, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    # Stray untracked scope marker at repo root.
    marker = os.path.join(repo, ".rabbit-scope-active-foo")
    open(marker, "w").close()

    if not _tracked_dirty(repo):
        fail("A: precondition — tracked tree should be dirty before cleanup")
    proc = _run(repo)
    if proc.returncode != 0:
        fail(f"A: cleanup exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("A: cleanup exited 0 on a known-leak tree")
    if os.path.exists(marker):
        fail("A: stray .rabbit-scope-active-foo marker not removed")
    else:
        ok("A: stray scope marker removed")
    if _tracked_dirty(repo):
        fail("A: tracked tree still dirty after cleanup (feature.json not restored)")
    else:
        ok("A: feature.json restored to HEAD; tree clean (Inv 5 would pass)")


# ---------------------------------------------------------------------------
# B — UNEXPECTED tracked dirt (a real spec.md edit) → refuse non-zero, preserve.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    with open(spec, "a") as f:
        f.write("a genuine human edit\n")
    before = open(spec).read()
    proc = _run(repo)
    if proc.returncode == 0:
        fail("B: cleanup MUST refuse (non-zero) on unexpected tracked dirt")
    else:
        ok("B: cleanup refused (non-zero) on unexpected tracked dirt")
    after = open(spec).read()
    if after != before:
        fail("B: cleanup discarded an unexpected tracked edit (DATA LOSS)")
    else:
        ok("B: unexpected spec.md edit preserved, not discarded")
    if "spec.md" not in proc.stderr:
        fail(f"B: stderr did not name the offending file; stderr={proc.stderr!r}")
    else:
        ok("B: stderr names the offending unexpected file")


# ---------------------------------------------------------------------------
# C — non-bookkeeping feature.json edit is ALSO unexpected → refuse, preserve.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    with open(fj) as f:
        data = json.load(f)
    data["tdd_last_cycle_impl_commit"] = "deadbeef"   # bookkeeping
    data["summary"] = "a real content change"          # NOT bookkeeping
    with open(fj, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    before = open(fj).read()
    proc = _run(repo)
    if proc.returncode == 0:
        fail("C: feature.json with a non-bookkeeping key change must NOT be restored")
    else:
        ok("C: cleanup refused on feature.json non-bookkeeping change")
    if open(fj).read() != before:
        fail("C: cleanup discarded a non-bookkeeping feature.json change (DATA LOSS)")
    else:
        ok("C: non-bookkeeping feature.json change preserved")


# ---------------------------------------------------------------------------
# D — clean tree → no-op (exit 0, nothing changed).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    proc = _run(repo)
    if proc.returncode != 0:
        fail(f"D: cleanup on a clean tree must be a no-op (exit 0); "
             f"stderr={proc.stderr!r}")
    else:
        ok("D: cleanup is a no-op on a clean tree (exit 0)")
    if _tracked_dirty(repo):
        fail("D: cleanup dirtied a clean tree")
    else:
        ok("D: clean tree stayed clean")


# ---------------------------------------------------------------------------
# E — cleanup logs what it cleaned (Inv 36 observability).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    with open(fj) as f:
        data = json.load(f)
    data["tdd_last_cycle_impl_commit"] = "deadbeef"
    with open(fj, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    open(os.path.join(repo, ".rabbit-scope-active-foo"), "w").close()
    proc = _run(repo)
    if proc.returncode != 0:
        fail(f"E: cleanup exit {proc.returncode}; stderr={proc.stderr!r}")
    log_path = os.path.join(repo, ".rabbit", "tick.log")
    if not os.path.isfile(log_path):
        fail("E: cleanup did not write a tick.log entry (Inv 36)")
    else:
        body = open(log_path).read()
        if "feature.json" not in body and "scope-active" not in body:
            fail(f"E: tick.log does not record what was cleaned; log={body!r}")
        else:
            ok("E: cleanup logged what it cleaned (Inv 36)")


# ---------------------------------------------------------------------------
# G — leaked HEAD switch (#596): HEAD on a feature branch whose commits are all
#     on its origin remote, clean tree → cleanup restores HEAD to main and logs.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    # A subagent leaked `git checkout -B feat/x origin/main` into the MAIN tree:
    # HEAD is on a feature branch, but it points at main's commit (already pushed
    # to origin/main) so there is no un-pushed unique work and the tree is clean.
    _git(repo, "checkout", "-B", "feat/leaked", "main")
    _git(repo, "push", "-u", "origin", "feat/leaked")
    if _head(repo) != "feat/leaked":
        fail("G: precondition — HEAD should be on feat/leaked before cleanup")
    proc = _run(repo)
    if proc.returncode != 0:
        fail(f"G: cleanup exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("G: cleanup exited 0 on a clean leaked-branch tree")
    if _head(repo) != "main":
        fail(f"G: HEAD not restored to main (still {_head(repo)!r})")
    else:
        ok("G: leaked HEAD switch restored to main")
    log_path = os.path.join(repo, ".rabbit", "tick.log")
    if not os.path.isfile(log_path) or "main" not in open(log_path).read():
        fail("G: branch restoration not logged (Inv 36)")
    else:
        ok("G: branch restoration logged (Inv 36)")


# ---------------------------------------------------------------------------
# H — leaked HEAD switch with a DIRTY tree → REFUSE (non-zero), do NOT switch
#     or discard. Mirrors the unexpected-dirt refusal.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    _git(repo, "checkout", "-B", "feat/leaked", "main")
    _git(repo, "push", "-u", "origin", "feat/leaked")
    with open(spec, "a") as f:
        f.write("a genuine human edit\n")
    before = open(spec).read()
    proc = _run(repo)
    if proc.returncode == 0:
        fail("H: cleanup MUST refuse (non-zero) when HEAD!=main AND tree dirty")
    else:
        ok("H: cleanup refused (non-zero) on dirty leaked-branch tree")
    if _head(repo) != "feat/leaked":
        fail(f"H: cleanup switched branch despite dirt (now {_head(repo)!r})")
    else:
        ok("H: cleanup did NOT switch branch while dirty")
    if open(spec).read() != before:
        fail("H: cleanup discarded an uncommitted edit (DATA LOSS)")
    else:
        ok("H: uncommitted edit preserved")


# ---------------------------------------------------------------------------
# I — leaked HEAD switch with an UN-PUSHED unique commit → REFUSE (non-zero),
#     do NOT switch or discard the un-pushed work.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    _git(repo, "checkout", "-B", "feat/leaked", "main")
    # A commit that exists ONLY on the local branch (never pushed to origin).
    with open(spec, "a") as f:
        f.write("local-only work\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "un-pushed unique work")
    unpushed_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    proc = _run(repo)
    if proc.returncode == 0:
        fail("I: cleanup MUST refuse when HEAD!=main AND branch has un-pushed work")
    else:
        ok("I: cleanup refused (non-zero) on un-pushed unique commit")
    if _head(repo) != "feat/leaked":
        fail(f"I: cleanup switched branch despite un-pushed work "
             f"(now {_head(repo)!r})")
    else:
        ok("I: cleanup did NOT switch branch with un-pushed work")
    if _git(repo, "cat-file", "-e", unpushed_sha).returncode != 0:
        fail("I: cleanup discarded an un-pushed commit (DATA LOSS)")
    else:
        ok("I: un-pushed commit preserved")


# ---------------------------------------------------------------------------
# J — HEAD already on main → branch-restore is a no-op (clean tree, exit 0).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    proc = _run(repo)
    if proc.returncode != 0:
        fail(f"J: clean main tree must be a no-op (exit 0); stderr={proc.stderr!r}")
    elif _head(repo) != "main":
        fail(f"J: HEAD changed off main on a no-op (now {_head(repo)!r})")
    else:
        ok("J: HEAD already on main → branch-restore is a no-op")


# ---------------------------------------------------------------------------
# K — leaked HEAD switch + a known file-leak class (stray marker) on a clean,
#     pushed feature branch → branch restored to main AND the marker removed.
#     Order matters: restore branch FIRST, then file cleanup.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp)
    _git(repo, "checkout", "-B", "feat/leaked", "main")
    _git(repo, "push", "-u", "origin", "feat/leaked")
    marker = os.path.join(repo, ".rabbit-scope-active-foo")
    open(marker, "w").close()
    proc = _run(repo)
    if proc.returncode != 0:
        fail(f"K: cleanup exit {proc.returncode}; stderr={proc.stderr!r}")
    if _head(repo) != "main":
        fail(f"K: HEAD not restored to main (still {_head(repo)!r})")
    else:
        ok("K: branch restored AND")
    if os.path.exists(marker):
        fail("K: stray marker not removed after branch restore")
    else:
        ok("K: file-leak cleanup still ran after branch restore")


# ---------------------------------------------------------------------------
# L — INTEGRATION-TARGET AWARENESS (post-cutover, target=main): HEAD already on
#     the resolved target `main` is NOT a leak → branch-restore is a no-op.
#     Hardcoding `dev` would WRONGLY treat the live `main` HEAD as leaked and
#     switch the dispatcher OFF main (Inv 44 / Inv 61).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp, target="main")
    proc = _run(repo, target="main")
    if proc.returncode != 0:
        fail(f"L: clean main tree (target=main) must be a no-op (exit 0); "
             f"stderr={proc.stderr!r}")
    elif _head(repo) != "main":
        fail(f"L: HEAD switched off the resolved target main (now {_head(repo)!r}) "
             f"— hardcoded-dev regression")
    else:
        ok("L: HEAD on resolved target main → branch-restore is a no-op "
           "(not treated as a leak)")


# ---------------------------------------------------------------------------
# M — INTEGRATION-TARGET AWARENESS (target=main): a leaked feature-branch
#     switch on a clean, pushed branch is restored to the RESOLVED target
#     `main`, NOT to a hardcoded `dev`.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp, target="main")
    _git(repo, "checkout", "-B", "feat/leaked", "main")
    _git(repo, "push", "-u", "origin", "feat/leaked")
    if _head(repo) != "feat/leaked":
        fail("M: precondition — HEAD should be on feat/leaked before cleanup")
    proc = _run(repo, target="main")
    if proc.returncode != 0:
        fail(f"M: cleanup exit {proc.returncode}; stderr={proc.stderr!r}")
    if _head(repo) != "main":
        fail(f"M: leaked HEAD not restored to resolved target main "
             f"(still {_head(repo)!r})")
    else:
        ok("M: leaked HEAD switch restored to resolved target main (Inv 61)")


# ---------------------------------------------------------------------------
# N — INTEGRATION-TARGET AWARENESS (target=main): the legacy `dev` branch, when
#     it is NOT the resolved target, IS treated as a leaked switch and restored
#     to `main`. (Post-cutover, sitting on `dev` is itself the leak.)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    repo, fj, spec = _make_repo(tmp, target="main")
    # Create a `dev` branch pointing at main's (pushed) commit and switch to it.
    _git(repo, "checkout", "-B", "dev", "main")
    _git(repo, "push", "-u", "origin", "dev")
    proc = _run(repo, target="main")
    if proc.returncode != 0:
        fail(f"N: cleanup exit {proc.returncode}; stderr={proc.stderr!r}")
    if _head(repo) != "main":
        fail(f"N: HEAD on non-target `dev` not restored to main "
             f"(still {_head(repo)!r})")
    else:
        ok("N: HEAD on legacy `dev` (not the resolved target) restored to main")


# ---------------------------------------------------------------------------
# F — --help smoke.
# ---------------------------------------------------------------------------
proc = subprocess.run([sys.executable, SCRIPT, "--help"],
                      capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"--help: exit {proc.returncode}; stderr={proc.stderr!r}")
elif "clean" not in (proc.stdout + proc.stderr).lower():
    fail("--help: usage text missing 'clean'")
else:
    ok("--help: clean-dispatch-leaks.py exits 0 with recognizable usage")


sys.exit(FAIL)
