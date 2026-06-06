#!/usr/bin/env python3
"""test-safety-check.py — e2e tests for scripts/safety-check.py (Inv 5).

Covers the five bottom-line safety invariants from design doc §9, phase-
gated per the spec:
  merge   → 1, 2, 5
  release → 1, 2, 4, 5
  cleanup → 1, 3, 5

For each invariant, one negative test isolates the violating state and
asserts non-zero exit + stderr line naming the violated invariant. One
positive test per phase asserts exit 0 when every required invariant
holds. Additional tests exercise the --next-tag required-when-release /
forbidden-elsewhere gating and the --help smoke contract.

Fixtures use a real `git init -b dev` in a tempdir plus a PATH-resident
`gh` shim that emits canned JSON for `gh pr view` calls. No live network.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "safety-check.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write_gh_shim(shim_dir, base_ref="dev", head_ref="feat/some-thing"):
    """Write a `gh` shim that emits canned JSON for `gh pr view --json
    baseRefName` and `--json headRefName`."""
    shim_path = os.path.join(shim_dir, "gh")
    with open(shim_path, "w") as f:
        f.write("#!/bin/sh\n")
        # Parse for `--json <name>` and emit the right field. We default
        # to baseRefName=dev, headRefName=feat/some-thing.
        f.write(f'BASE_REF={base_ref}\n')
        f.write(f'HEAD_REF={head_ref}\n')
        # Walk args for --json and -q
        f.write('JSON_FIELDS=""\n')
        f.write('QUERY=""\n')
        f.write('while [ "$#" -gt 0 ]; do\n')
        f.write('  case "$1" in\n')
        f.write('    --json) JSON_FIELDS="$2"; shift 2 ;;\n')
        f.write('    -q) QUERY="$2"; shift 2 ;;\n')
        f.write('    *) shift ;;\n')
        f.write('  esac\n')
        f.write('done\n')
        # Emit just the requested field as a raw string (if -q .<field>),
        # else emit JSON.
        f.write('case "$QUERY" in\n')
        f.write('  .baseRefName) printf "%s\\n" "$BASE_REF" ;;\n')
        f.write('  .headRefName) printf "%s\\n" "$HEAD_REF" ;;\n')
        f.write('  *)\n')
        f.write('    case "$JSON_FIELDS" in\n')
        f.write('      *baseRefName*) printf \'{"baseRefName":"%s"}\\n\' "$BASE_REF" ;;\n')
        f.write('      *headRefName*) printf \'{"headRefName":"%s"}\\n\' "$HEAD_REF" ;;\n')
        f.write('      *) printf "{}\\n" ;;\n')
        f.write('    esac\n')
        f.write('    ;;\n')
        f.write('esac\n')
    os.chmod(shim_path, stat.S_IRWXU)


def _make_clean_repo(tmpdir, base_ref="dev", head_ref="feat/some-thing",
                     init_branch="dev", integration_target=None):
    """Create a tempdir-local git repo on branch `init_branch` (default
    `dev`), with an initial commit, and a `gh` shim on PATH. Return (cwd, env).

    `integration_target` (Inv 61): when None the env var is cleared so the
    check resolves the coexistence default (`dev`); set it to 'dev'/'main' to
    drive the resolved integration target Inv 1/2 assert against."""
    repo = os.path.join(tmpdir, "repo")
    os.makedirs(repo)
    shim_dir = os.path.join(tmpdir, "bin")
    os.makedirs(shim_dir)
    _write_gh_shim(shim_dir, base_ref=base_ref, head_ref=head_ref)

    env = os.environ.copy()
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["HOME"] = tmpdir  # isolate user git config
    env["GIT_AUTHOR_NAME"] = "tester"
    env["GIT_AUTHOR_EMAIL"] = "tester@example.com"
    env["GIT_COMMITTER_NAME"] = "tester"
    env["GIT_COMMITTER_EMAIL"] = "tester@example.com"
    env.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
    if integration_target is not None:
        env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = integration_target

    # Init repo on `init_branch` and make a commit so HEAD exists.
    subprocess.run(["git", "init", "-b", init_branch, repo],
                   check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", repo, "commit", "--allow-empty", "-m", "init"],
                   check=True, capture_output=True, env=env)
    return repo, env


def _run(repo, env, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=repo, env=env, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail(f"help: 'usage' missing; stdout={proc.stdout!r} stderr={proc.stderr!r}")
else:
    ok("help: usage text present")


# ---------------------------------------------------------------------------
# --next-tag gating
#   REQUIRED iff --phase release; FORBIDDEN for merge / cleanup.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)

    # Missing --next-tag under --phase release → argparse error, non-zero.
    proc = _run(repo, env, "42", "--phase", "release")
    if proc.returncode == 0:
        fail("next-tag-required: release without --next-tag should fail")
    else:
        ok("next-tag-required: release without --next-tag exits non-zero")

    # --next-tag passed under --phase merge → non-zero (forbidden).
    proc = _run(repo, env, "42", "--phase", "merge", "--next-tag", "v1.2.3")
    if proc.returncode == 0:
        fail("next-tag-forbidden-merge: merge with --next-tag should fail")
    else:
        ok("next-tag-forbidden-merge: merge with --next-tag exits non-zero")

    # --next-tag passed under --phase cleanup → non-zero (forbidden).
    proc = _run(repo, env, "42", "--phase", "cleanup", "--next-tag", "v1.2.3")
    if proc.returncode == 0:
        fail("next-tag-forbidden-cleanup: cleanup with --next-tag should fail")
    else:
        ok("next-tag-forbidden-cleanup: cleanup with --next-tag exits non-zero")


# ---------------------------------------------------------------------------
# Positive: every phase passes when all required invariants hold.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)

    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode != 0:
        fail(f"merge-positive: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("merge-positive: clean state on dev passes merge phase")

    proc = _run(repo, env, "42", "--phase", "release", "--next-tag", "v9.9.9")
    if proc.returncode != 0:
        fail(f"release-positive: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("release-positive: clean state + unused tag passes release phase")

    proc = _run(repo, env, "42", "--phase", "cleanup")
    if proc.returncode != 0:
        fail(f"cleanup-positive: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("cleanup-positive: clean state + feat/ head passes cleanup phase")


# ---------------------------------------------------------------------------
# Inv 1 negative — current git branch is not the integration target.
#   During the dev<->main coexistence window the branch must be dev OR main;
#   any other branch (e.g. release/x) fails Inv 1. Run under --phase merge.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    subprocess.run(["git", "-C", repo, "checkout", "-b", "release/x"],
                   check=True, capture_output=True, env=env)
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv1: on release/x branch should fail")
    elif "Invariant 1" not in proc.stderr:
        fail(f"inv1: stderr should name 'Invariant 1'; got {proc.stderr!r}")
    else:
        ok("inv1: on release/x branch fails with 'Invariant 1' in stderr")


# ---------------------------------------------------------------------------
# Inv 1 coexistence (Inv 61) — current branch == main is ACCEPTED while the
# resolved integration target is main. Init the repo on main, set the target.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, base_ref="main", init_branch="main",
                                 integration_target="main")
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode != 0:
        fail(f"inv1-coexist-main: branch=main target=main should pass; "
             f"got exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("inv1-coexist-main: branch==main passes when target=main")


# ---------------------------------------------------------------------------
# Inv 2 negative — PR base branch is not the integration target.
#   A base outside the accepted {dev, main} coexistence set (e.g. release/x)
#   fails Inv 2. Run under --phase merge.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, base_ref="release/x")
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv2: PR base=release/x should fail")
    elif "Invariant 2" not in proc.stderr:
        fail(f"inv2: stderr should name 'Invariant 2'; got {proc.stderr!r}")
    else:
        ok("inv2: PR base=release/x fails with 'Invariant 2' in stderr")


# ---------------------------------------------------------------------------
# Inv 2 coexistence (Inv 61) — PR base==main is ACCEPTED while the resolved
# integration target is main (init the repo on main so Inv 1 also holds).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, base_ref="main", init_branch="main",
                                 integration_target="main")
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode != 0:
        fail(f"inv2-coexist-main: base=main target=main should pass merge; "
             f"got exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("inv2-coexist-main: base==main passes merge when target=main")


# ---------------------------------------------------------------------------
# Inv 3 negative — PR head branch does not match ^feat/.+.
#   Run under --phase cleanup with gh shim emitting head=hotfix/foo.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, head_ref="hotfix/foo")
    proc = _run(repo, env, "42", "--phase", "cleanup")
    if proc.returncode == 0:
        fail("inv3-pattern: head=hotfix/foo should fail cleanup phase")
    elif "Invariant 3" not in proc.stderr:
        fail(f"inv3-pattern: stderr should name 'Invariant 3'; got {proc.stderr!r}")
    else:
        ok("inv3-pattern: head=hotfix/foo fails with 'Invariant 3' in stderr")

# Inv 3 negative — head is `dev` itself.
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, head_ref="dev")
    proc = _run(repo, env, "42", "--phase", "cleanup")
    if proc.returncode == 0:
        fail("inv3-dev: head=dev should fail cleanup phase")
    elif "Invariant 3" not in proc.stderr:
        fail(f"inv3-dev: stderr should name 'Invariant 3'; got {proc.stderr!r}")
    else:
        ok("inv3-dev: head=dev fails with 'Invariant 3' in stderr")

# Inv 3 negative — head is `release/...`.
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, head_ref="release/v1.0.0")
    proc = _run(repo, env, "42", "--phase", "cleanup")
    if proc.returncode == 0:
        fail("inv3-release: head=release/* should fail cleanup phase")
    elif "Invariant 3" not in proc.stderr:
        fail(f"inv3-release: stderr should name 'Invariant 3'; got {proc.stderr!r}")
    else:
        ok("inv3-release: head=release/v1.0.0 fails with 'Invariant 3' in stderr")


# ---------------------------------------------------------------------------
# Inv 4 negative — the --next-tag tag already exists.
#   Run under --phase release; create the tag first.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    subprocess.run(["git", "-C", repo, "tag", "v1.2.3"],
                   check=True, capture_output=True, env=env)
    proc = _run(repo, env, "42", "--phase", "release", "--next-tag", "v1.2.3")
    if proc.returncode == 0:
        fail("inv4: pre-existing tag should fail release phase")
    elif "Invariant 4" not in proc.stderr:
        fail(f"inv4: stderr should name 'Invariant 4'; got {proc.stderr!r}")
    else:
        ok("inv4: pre-existing tag fails with 'Invariant 4' in stderr")


# ---------------------------------------------------------------------------
# Inv 5 — tracked-file dirtiness only (issue #397).
#   Inv 5 must reject only on uncommitted modifications to TRACKED files
#   (staged or unstaged). Untracked files (`??`) cannot affect a merge and
#   MUST NOT trip Inv 5 — otherwise the auto-evolve loop deadlocks every
#   time a new runtime artifact appears.
# ---------------------------------------------------------------------------

# (a) Untracked file in working tree → Inv 5 PASSES (merge phase exits 0).
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    with open(os.path.join(repo, "untracked-file"), "w") as f:
        f.write("untracked\n")
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode != 0:
        fail(f"inv5-untracked: untracked file should NOT fail merge phase; "
             f"got exit {proc.returncode}; stderr={proc.stderr!r}")
    elif "Invariant 5" in proc.stderr:
        fail(f"inv5-untracked: stderr must not name 'Invariant 5'; "
             f"got {proc.stderr!r}")
    else:
        ok("inv5-untracked: untracked file passes merge phase")

# (b) Tracked file with an unstaged modification → Inv 5 FAILS.
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    tracked = os.path.join(repo, "tracked.txt")
    with open(tracked, "w") as f:
        f.write("original\n")
    subprocess.run(["git", "-C", repo, "add", "tracked.txt"],
                   check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", repo, "commit", "-m", "add tracked"],
                   check=True, capture_output=True, env=env)
    with open(tracked, "w") as f:
        f.write("modified\n")  # unstaged modification
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv5-unstaged: tracked file with unstaged mod should fail "
             "merge phase")
    elif "Invariant 5" not in proc.stderr:
        fail(f"inv5-unstaged: stderr should name 'Invariant 5'; "
             f"got {proc.stderr!r}")
    else:
        ok("inv5-unstaged: tracked unstaged modification fails with "
           "'Invariant 5' in stderr")

# (c) Tracked file with a staged modification → Inv 5 FAILS.
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    tracked = os.path.join(repo, "tracked.txt")
    with open(tracked, "w") as f:
        f.write("original\n")
    subprocess.run(["git", "-C", repo, "add", "tracked.txt"],
                   check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", repo, "commit", "-m", "add tracked"],
                   check=True, capture_output=True, env=env)
    with open(tracked, "w") as f:
        f.write("modified\n")
    subprocess.run(["git", "-C", repo, "add", "tracked.txt"],
                   check=True, capture_output=True, env=env)  # staged
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv5-staged: tracked file with staged mod should fail "
             "merge phase")
    elif "Invariant 5" not in proc.stderr:
        fail(f"inv5-staged: stderr should name 'Invariant 5'; "
             f"got {proc.stderr!r}")
    else:
        ok("inv5-staged: tracked staged modification fails with "
           "'Invariant 5' in stderr")

# (d) Clean tree (no tracked mods, no untracked files) → Inv 5 PASSES.
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode != 0:
        fail(f"inv5-clean: clean tree should pass merge phase; "
             f"got exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("inv5-clean: clean tree passes merge phase")


# ---------------------------------------------------------------------------
# Phase-gating check — a violation of an invariant NOT enforced by the
# selected phase should NOT cause a non-zero exit.
#   --phase merge ignores Inv 3 (head-branch shape); violating only Inv 3
#   should still exit 0.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, head_ref="hotfix/foo")
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode != 0:
        fail(f"phase-gating-merge: violating only Inv 3 should NOT fail "
             f"merge; got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("phase-gating-merge: Inv 3 violation does not fail merge phase")

#   --phase cleanup ignores Inv 2 (PR base); violating only Inv 2 should
#   still exit 0.
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, base_ref="main")
    proc = _run(repo, env, "42", "--phase", "cleanup")
    if proc.returncode != 0:
        fail(f"phase-gating-cleanup: violating only Inv 2 should NOT fail "
             f"cleanup; got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("phase-gating-cleanup: Inv 2 violation does not fail cleanup phase")


# ---------------------------------------------------------------------------
# Bottom-line check 6 (spec Inv 63 / issue #966) — the merge phase runs the
# install smoke and BLOCKS on a failure. The smoke is delegated to the sibling
# install-smoke.py, overridable for tests via RABBIT_AUTO_EVOLVE_INSTALL_SMOKE.
# The release and cleanup phases do NOT run the smoke.
# ---------------------------------------------------------------------------

def _write_smoke_shim(shim_dir, exit_code):
    """Write a fake install-smoke.py that just exits `exit_code`."""
    import stat as _stat
    path = os.path.join(shim_dir, "install-smoke.py")
    with open(path, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import sys\n")
        if exit_code != 0:
            f.write("sys.stderr.write('install-smoke: simulated failure\\n')\n")
        f.write(f"sys.exit({exit_code})\n")
    os.chmod(path, _stat.S_IRWXU)
    return path

# (a) merge phase BLOCKS when the install smoke fails (non-zero).
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    shim = _write_smoke_shim(td, 7)
    env["RABBIT_AUTO_EVOLVE_INSTALL_SMOKE"] = shim
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv6-merge-block: failing install smoke should fail merge phase")
    elif "Invariant 6" not in proc.stderr:
        fail(f"inv6-merge-block: stderr should name 'Invariant 6'; "
             f"got {proc.stderr!r}")
    else:
        ok("inv6-merge-block: failing install smoke fails merge with "
           "'Invariant 6' in stderr")

# (b) merge phase PASSES when the install smoke passes (exit 0).
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    shim = _write_smoke_shim(td, 0)
    env["RABBIT_AUTO_EVOLVE_INSTALL_SMOKE"] = shim
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode != 0:
        fail(f"inv6-merge-pass: passing install smoke should pass merge; "
             f"got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("inv6-merge-pass: passing install smoke passes merge phase")

# (c) release / cleanup phases do NOT run the install smoke — a failing shim
#     does not affect them (the install smoke is merge-only).
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    shim = _write_smoke_shim(td, 7)
    env["RABBIT_AUTO_EVOLVE_INSTALL_SMOKE"] = shim
    proc = _run(repo, env, "42", "--phase", "release", "--next-tag", "v9.9.9")
    if "install smoke" in proc.stderr.lower():
        fail(f"inv6-release-skip: release phase must NOT run install smoke; "
             f"got {proc.stderr!r}")
    else:
        ok("inv6-release-skip: release phase does not run the install smoke")
    proc = _run(repo, env, "42", "--phase", "cleanup")
    if "install smoke" in proc.stderr.lower():
        fail(f"inv6-cleanup-skip: cleanup phase must NOT run install smoke; "
             f"got {proc.stderr!r}")
    else:
        ok("inv6-cleanup-skip: cleanup phase does not run the install smoke")


sys.exit(FAIL)
