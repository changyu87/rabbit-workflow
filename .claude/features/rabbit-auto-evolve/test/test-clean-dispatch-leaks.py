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

Fixtures use a real `git init -b dev` in a tempdir. No live network.
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


def _make_repo(tmp):
    """A git repo on `dev` with a committed feature.json under a feature dir."""
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    _git(repo, "init", "-b", "dev")
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
    return repo, fj, spec


def _run(repo):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(repo, ".rabbit")
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
