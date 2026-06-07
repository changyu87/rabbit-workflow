#!/usr/bin/env python3
"""install-smoke.py — isolated pre-merge install + update smoke test (Inv 66).

Usage:
  install-smoke.py [--repo-root <dir>]

Runs an ISOLATED, deterministic, network-free smoke test of rabbit-cage's
`install.py` against the CURRENT tree, so install/closure breakage is caught
BEFORE a PR merges (issue #966). This session saw install regressions slip
into dev that a per-merge install smoke would have caught:
`--update` closure-shrink failures and fresh-install `publish_file ... source
not found` aborts. The smoke is wired into the pre-merge safety gate
(`safety-check.py --phase merge`, Inv 66) so a smoke FAILURE blocks the merge.

What it does (in a `tempfile.TemporaryDirectory()`, cleaned up on exit):
  1. FRESH install: `install.py --src <repo-root> --target <tmp>/fresh`.
     Asserts exit 0 AND that the combined stdout+stderr contains NO
     install-failure signature (`source not found`, `publish failure`,
     `closure` error wording, etc.).
  2. UPDATE smoke: `install.py --src <repo-root> --target <tmp>/fresh
     --update` against the SAME freshly-installed target. Asserts exit 0 and
     no failure signature — this exercises the `--update` refresh path that
     drives the OLD install with its (possibly stale) closure.

Both invocations pass `--src <repo-root>` explicitly so the smoke is fully
offline (no self-fetch / no network). install.py is invoked as a BLACK BOX
subprocess — this is a contract INVOKE of rabbit-cage, never an edit.

Resolution:
  - The repo root defaults to the repo inferred from this script's path
    (`.claude/features/rabbit-auto-evolve/scripts/` → repo root), overridable
    via `--repo-root` or the `RABBIT_AUTO_EVOLVE_REPO_ROOT` env var.
  - install.py is resolved at `<repo-root>/.claude/features/rabbit-cage/
    install.py`, overridable via the `RABBIT_AUTO_EVOLVE_INSTALL_PY` env var
    (a test seam to inject a shim install.py without touching the real one).

Resilient SKIP (matches contract Inv 64/65): if install.py cannot be found
(a degenerate self-build, or the isolated git tempdirs the safety-check tests
run in), the smoke SKIPS gracefully — exit 0, a `skipped` note on stderr —
rather than failing. In the normal repo install.py is present and the smoke
MUST run and pass.

Exit code: 0 on pass or skip; non-zero on any smoke FAILURE. On failure the
failing phase (`fresh` / `update`), the install exit code, and the offending
output are written to stderr.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import os
import subprocess
import sys
import tempfile

# Output substrings that signal an install / closure / publish failure even
# when install.py's exit code happens to be 0. Lower-cased before matching.
FAILURE_SIGNATURES = (
    "source not found",
    "missing required source file",
    "publish failure",
    "publish failed",
    "install closure references source files absent",
    "closure error",
    "dangling",
)


def _resolve_repo_root(arg_root):
    if arg_root:
        return os.path.abspath(arg_root)
    env_root = os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    # this script lives at .claude/features/rabbit-auto-evolve/scripts/
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


def _resolve_install_py(repo_root):
    override = os.environ.get("RABBIT_AUTO_EVOLVE_INSTALL_PY")
    if override:
        return override
    return os.path.join(
        repo_root, ".claude", "features", "rabbit-cage", "install.py"
    )


def _has_failure_signature(text):
    low = text.lower()
    for sig in FAILURE_SIGNATURES:
        if sig in low:
            return sig
    return None


def _run_install(install_py, args):
    """Run install.py with `args`; return (returncode, combined_output)."""
    proc = subprocess.run(
        [sys.executable, install_py, *args],
        capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _report_failure(phase, rc, output, sig=None):
    sys.stderr.write(
        f"install-smoke: {phase} install FAILED "
        f"(exit {rc}"
        + (f", signature {sig!r}" if sig else "")
        + "):\n"
    )
    sys.stderr.write(output.rstrip() + "\n")


def smoke(repo_root):
    """Run the fresh + update install smoke. Return 0 on pass/skip, non-zero
    on failure. Self-contained; cleans up its tempdir."""
    install_py = _resolve_install_py(repo_root)
    if not os.path.isfile(install_py):
        sys.stderr.write(
            f"install-smoke: skipped — install.py not found at {install_py}\n"
        )
        return 0

    with tempfile.TemporaryDirectory(prefix="rabbit-install-smoke-") as td:
        target = os.path.join(td, "fresh")

        # 1. fresh install
        rc, out = _run_install(
            install_py, ["--src", repo_root, "--target", target]
        )
        if rc != 0:
            _report_failure("fresh", rc, out)
            return 1
        sig = _has_failure_signature(out)
        if sig:
            _report_failure("fresh", rc, out, sig)
            return 1

        # 2. update smoke against the same freshly-installed target
        rc, out = _run_install(
            install_py,
            ["--src", repo_root, "--target", target, "--update"],
        )
        if rc != 0:
            _report_failure("update", rc, out)
            return 1
        sig = _has_failure_signature(out)
        if sig:
            _report_failure("update", rc, out, sig)
            return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Isolated, network-free pre-merge install + update smoke "
                    "test of rabbit-cage's install.py against the current "
                    "tree (Inv 66). Exit 0 on pass or skip; non-zero on any "
                    "install/closure/publish failure. install.py is invoked "
                    "as a black box (a contract INVOKE, never an edit)."
    )
    parser.add_argument(
        "--repo-root", default=None,
        help="repo root used as install --src (default: inferred from this "
             "script's path; RABBIT_AUTO_EVOLVE_REPO_ROOT overrides)",
    )
    args = parser.parse_args()
    repo_root = _resolve_repo_root(args.repo_root)
    sys.exit(smoke(repo_root))


if __name__ == "__main__":
    main()
