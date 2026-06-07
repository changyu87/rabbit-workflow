#!/usr/bin/env python3
"""test-install-update-tolerates-closure-shrink.py — e2e: install.py --update
TOLERATES a closure that SHRINKS across a surface retirement, while a fresh
install still HARD-FAILS on any dangling source and an --update whose NEW
closure requires a missing source still HARD-FAILS (Inv 49, bug #968).

Bug shape: `install.py --update` is driven by the LOCALLY-installed (older)
install.py, whose hardcoded closure still names surfaces the NEW upstream
source has RETIRED. The fresh-install integrity self-check (Inv 21) treated
EVERY closure source absent from --src as a hard "dangling required-file"
abort, so a release crossing a retirement was permanently un-installable from
an older install — the stale local closure could never be reconciled before
the re-exec into the new install.py (Inv 22h). A FRESH install from the same
new source SUCCEEDED, confirming the failure was specific to the --update
path crossing a retirement.

Fix (Inv 49): the integrity gate is ASYMMETRIC by mode.
  (a) Fresh install (no --update): unchanged — HARD-ABORT on any absent
      closure source.
  (b) --update pre-re-exec (self-fetch window, OLD/stale closure): a source
      absent from the NEW --src is a TOLERATED closure SHRINK — dropped, not
      aborted — so the in-place refresh proceeds to the re-exec, after which
      the NEW install.py validates its OWN corrected closure against the NEW
      source.
  (c) --update post-re-exec (NEW closure): a path the NEW closure REQUIRES
      but the NEW source omits is a REAL dangling ref and still HARD-FAILS.

The re-exec path tests run install.py as a SUBPROCESS so os.execv is real;
they reuse the tarball-via-patched-fetch_upstream mechanism from
test-install-update-self-reexec.py. The fresh-install hard-fail test calls
install.main() in-process (no re-exec on the fresh path).
"""

from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_shrink_check", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_src_tree(src_root: Path, mod) -> None:
    """Build a complete src tree mirroring the repo layout — full closure."""
    def _copy_rel(rel: str) -> None:
        # Source-of-truth for install.py is the feature copy, not the deployed
        # root copy (the root copy is a sync artifact that may lag the feature
        # source between IMPLEMENT and SYNC-DEPLOYED).
        s = INSTALL_PY if rel == "install.py" else REPO / rel
        d = src_root / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    for rel in mod.SAME_PATH_FILES:
        _copy_rel(rel)
    for src_rel, _dst in mod.HOOKS:
        _copy_rel(src_rel)
    for src_rel, _dst in mod.SKILLS:
        _copy_rel(src_rel)
    for src_rel, _dst in mod.AGENTS:
        _copy_rel(src_rel)
    for src_rel, _dst in mod.COMMANDS:
        _copy_rel(src_rel)
    for feature, paths in mod.FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        for rel in paths:
            _copy_rel(f"{base}/{rel}")


def _patch_fetch_upstream_to_return(install_text: str, fixture: Path) -> str:
    """Replace fetch_upstream's body with a stub returning `fixture`, so the
    self-fetch path resolves to the local fixture without any network. Mirrors
    the mechanism in test-install-update-self-reexec.py."""
    marker = "def fetch_upstream(repo: str, ref: str, dest: Path) -> Path:"
    assert marker in install_text, "fetch_upstream signature not found"
    override = (
        marker + "\n"
        "    from pathlib import Path as _P\n"
        f"    return _P({str(fixture)!r})\n"
        "    # original body suppressed for test"
    )
    return install_text.replace(marker, override, 1)


def _run_subprocess_update(install_under_test: Path, target: Path) -> subprocess.CompletedProcess:
    """Run a shim that loads `install_under_test` and calls main(--update)
    without --src, forcing the self-fetch + re-exec path."""
    shim = target.parent / "shim.py"
    shim.write_text(
        "import sys, importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('install', {str(install_under_test)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        f"sys.argv = ['install.py', '--update', '--target', {str(target)!r}]\n"
        "sys.exit(mod.main())\n"
    )
    env = os.environ.copy()
    env.pop("RABBIT_INSTALL_REEXEC_DONE", None)
    return subprocess.run(
        [sys.executable, str(shim)], capture_output=True, text=True, env=env
    )


# --- (b) tolerated shrink: --update across a retirement SUCCEEDS ----------

def test_update_tolerates_retired_surface():
    """The OLD (deployed) install.py's closure names a source the NEW --src
    has RETIRED. The --update MUST succeed: the retired entry is dropped, the
    re-exec into the NEW install.py runs the corrected closure, and the
    retired surface is NOT present in the refreshed install."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()

        # 1. NEW source tree (full upstream content).
        new_src = td_path / "new_src"
        new_src.mkdir()
        _build_src_tree(new_src, mod)

        # 2. Fresh install at dst from the NEW source.
        dst = td_path / "dst"
        rc = subprocess.run(
            [sys.executable, str(INSTALL_PY), "--src", str(new_src), "--target", str(dst)],
            capture_output=True, text=True,
        ).returncode
        assert rc == 0, "fresh install setup failed"

        # 3. Simulate a RETIREMENT: the OLD deployed install.py still names a
        #    surface that the NEW source no longer ships. We add a stale entry
        #    to the OLD (deployed) install.py's SAME_PATH_FILES pointing at a
        #    retired file, create that file in the OLD install so the OLD
        #    closure looks self-consistent locally, and DELETE it from the
        #    NEW source so the NEW source legitimately lacks it.
        retired_rel = ".claude/features/rabbit-cage/RETIRED-SURFACE.txt"
        # Plant the retired file in the OLD install only.
        (dst / retired_rel).parent.mkdir(parents=True, exist_ok=True)
        (dst / retired_rel).write_text("retired surface content\n")
        # Ensure the NEW source does NOT contain it (it never did).
        assert not (new_src / retired_rel).exists()

        # 4. Build the OLD install.py text: inject the retired entry into
        #    SAME_PATH_FILES and stub fetch_upstream to return new_src.
        old_text = (dst / "install.py").read_text()
        # Inject the retired rel as the FIRST SAME_PATH_FILES element.
        sp_marker = "SAME_PATH_FILES = ["
        assert sp_marker in old_text
        old_text = old_text.replace(
            sp_marker, sp_marker + f'\n    "{retired_rel}",', 1
        )
        old_text = _patch_fetch_upstream_to_return(old_text, new_src)
        (dst / "install.py").write_text(old_text)

        # The NEW source's install.py must ALSO stub fetch_upstream (the
        # re-exec'd new process self-fetches again) — but it MUST keep its
        # clean (no retired entry) closure so it represents the corrected
        # upstream closure.
        new_text = _patch_fetch_upstream_to_return((new_src / "install.py").read_text(), new_src)
        assert retired_rel not in new_text, "new closure must NOT name the retired surface"
        (new_src / "install.py").write_text(new_text)

        # 5. Run the OLD install.py --update (self-fetch path). The OLD closure
        #    names the retired file absent from new_src — pre-fix this aborts
        #    with the dangling-required-file error; post-fix it is tolerated.
        result = _run_subprocess_update(dst / "install.py", dst)
        assert result.returncode == 0, (
            "--update across a surface retirement MUST succeed (tolerated "
            f"closure shrink); got rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Pre-fix failure signature must be absent.
        assert "dangling required-file" not in result.stderr, (
            "the retired surface must NOT trigger a dangling-required-file "
            f"abort under --update.\nstderr: {result.stderr}"
        )
        # The re-exec must have happened (proof the NEW closure drove the rest).
        assert "re-execing into" in result.stderr, (
            f"re-exec did not fire.\nstderr: {result.stderr}"
        )
    print("PASS test_update_tolerates_retired_surface")


# --- (c) over-tolerance guard: NEW closure requires a missing source ------

def test_update_hard_fails_on_real_dangling_in_new_closure():
    """A path the NEW (post-re-exec) closure REQUIRES but the NEW source omits
    is a REAL dangling ref, not a retirement, and MUST still HARD-FAIL the
    --update. This proves the tolerance is scoped to the shrink and does not
    weaken the integrity check for genuine packaging defects."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()

        new_src = td_path / "new_src"
        new_src.mkdir()
        _build_src_tree(new_src, mod)

        dst = td_path / "dst"
        rc = subprocess.run(
            [sys.executable, str(INSTALL_PY), "--src", str(new_src), "--target", str(dst)],
            capture_output=True, text=True,
        ).returncode
        assert rc == 0, "fresh install setup failed"

        # The NEW closure REQUIRES a file the NEW source does NOT contain.
        # Inject the bogus entry into the NEW source's install.py SAME_PATH_FILES
        # (so the corrected, post-re-exec closure demands it) but never create
        # the file in new_src.
        bogus_rel = ".claude/features/rabbit-cage/REQUIRED-BUT-MISSING.txt"
        assert not (new_src / bogus_rel).exists()
        new_text = (new_src / "install.py").read_text()
        sp_marker = "SAME_PATH_FILES = ["
        assert sp_marker in new_text
        new_text = new_text.replace(
            sp_marker, sp_marker + f'\n    "{bogus_rel}",', 1
        )
        new_text = _patch_fetch_upstream_to_return(new_text, new_src)
        (new_src / "install.py").write_text(new_text)

        # The OLD deployed install.py also stubs fetch_upstream -> new_src but
        # keeps its clean closure (the bogus entry is upstream-only). The
        # pre-re-exec OLD code tolerates its own shrink; after re-exec the NEW
        # code's strict check sees its own closure requires the missing file.
        old_text = _patch_fetch_upstream_to_return((dst / "install.py").read_text(), new_src)
        (dst / "install.py").write_text(old_text)

        result = _run_subprocess_update(dst / "install.py", dst)
        assert result.returncode != 0, (
            "--update whose NEW closure REQUIRES a source absent from the NEW "
            "source MUST hard-fail (over-tolerance guard); got rc=0\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert bogus_rel in result.stderr, (
            "the genuinely-missing required source must be named in the abort "
            f"message.\nstderr: {result.stderr}"
        )
    print("PASS test_update_hard_fails_on_real_dangling_in_new_closure")


# --- (a) fresh install still HARD-FAILS on any dangling source ------------

def test_fresh_install_hard_fails_on_dangling_source():
    """A fresh install (no --update) against a source missing a required
    closure source MUST hard-abort (exit 1) naming the offending path —
    unchanged Inv 21 behavior; the tolerance is --update-only."""
    mod = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, mod)
        dst = td_path / "dst"

        bogus_rel = ".claude/features/rabbit-cage/FRESH-MISSING.txt"
        assert not (src / bogus_rel).exists()

        saved = list(mod.SAME_PATH_FILES)
        try:
            mod.SAME_PATH_FILES = saved + [bogus_rel]
            out, err = io.StringIO(), io.StringIO()
            saved_argv = sys.argv
            sys.argv = ["install.py", "--src", str(src), "--target", str(dst)]
            try:
                with redirect_stdout(out), redirect_stderr(err):
                    rc = mod.main()
            finally:
                sys.argv = saved_argv
        finally:
            mod.SAME_PATH_FILES = saved

        assert rc == 1, (
            "fresh install against a source missing a required closure source "
            f"MUST hard-abort (exit 1); got rc={rc}\nstderr: {err.getvalue()}"
        )
        assert bogus_rel in err.getvalue(), (
            "the offending dangling path must be named on a fresh install "
            f"abort.\nstderr: {err.getvalue()}"
        )
        assert "dangling required-file" in err.getvalue(), (
            f"fresh install must report the dangling-required-file class.\n"
            f"stderr: {err.getvalue()}"
        )
    print("PASS test_fresh_install_hard_fails_on_dangling_source")


def main() -> int:
    test_update_tolerates_retired_surface()
    test_update_hard_fails_on_real_dangling_in_new_closure()
    test_fresh_install_hard_fails_on_dangling_source()
    print("ALL PASSED test-install-update-tolerates-closure-shrink.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
