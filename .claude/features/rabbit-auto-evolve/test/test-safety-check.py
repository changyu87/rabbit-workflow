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


def _make_clean_repo(tmpdir, base_ref="dev", head_ref="feat/some-thing"):
    """Create a tempdir-local git repo on branch `dev`, with an initial
    commit, and a `gh` shim on PATH. Return (cwd, env)."""
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

    # Init repo on `dev` and make a commit so HEAD exists.
    subprocess.run(["git", "init", "-b", "dev", repo],
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
# Inv 1 negative — current git branch is not `dev`.
#   Run under --phase merge; should detect branch != dev.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    subprocess.run(["git", "-C", repo, "checkout", "-b", "main"],
                   check=True, capture_output=True, env=env)
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv1: on main branch should fail")
    elif "Invariant 1" not in proc.stderr:
        fail(f"inv1: stderr should name 'Invariant 1'; got {proc.stderr!r}")
    else:
        ok("inv1: on main branch fails with 'Invariant 1' in stderr")


# ---------------------------------------------------------------------------
# Inv 2 negative — PR base branch is not `dev`.
#   Run under --phase merge with gh shim emitting baseRefName=main.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td, base_ref="main")
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv2: PR base=main should fail")
    elif "Invariant 2" not in proc.stderr:
        fail(f"inv2: stderr should name 'Invariant 2'; got {proc.stderr!r}")
    else:
        ok("inv2: PR base=main fails with 'Invariant 2' in stderr")


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
# Inv 5 negative — working tree dirty.
#   Run under --phase merge with an untracked file present.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    repo, env = _make_clean_repo(td)
    with open(os.path.join(repo, "dirty-file"), "w") as f:
        f.write("dirty\n")
    proc = _run(repo, env, "42", "--phase", "merge")
    if proc.returncode == 0:
        fail("inv5: dirty tree should fail merge phase")
    elif "Invariant 5" not in proc.stderr:
        fail(f"inv5: stderr should name 'Invariant 5'; got {proc.stderr!r}")
    else:
        ok("inv5: dirty tree fails with 'Invariant 5' in stderr")


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


sys.exit(FAIL)
