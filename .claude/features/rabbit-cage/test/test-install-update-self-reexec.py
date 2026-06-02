#!/usr/bin/env python3
"""test-install-update-self-reexec.py — e2e: install.py --update re-execs
into the freshly-copied install.py before the FEATURE_INCLUDES loop runs
(Inv 22h, bug #297).

The bug: when the user runs `install.py --update`, the in-memory interpreter
is still executing the OLD install.py with the OLD FEATURE_INCLUDES /
SAME_PATH_FILES constants — even after the SAME_PATH_FILES loop copies the
NEW install.py to disk. Any closure entries added in the upstream release
are silently skipped because the in-memory dict doesn't know about them.

Fix: after the SAME_PATH_FILES copy step writes the new install.py to disk,
and BEFORE the FEATURE_INCLUDES loop runs, os.execv into the freshly-copied
install.py with the same sys.argv so the rest of the install uses the new
code.

This test runs install.py --update as a SUBPROCESS so the os.execv is real
(in-process re-exec would clobber the test harness). The "old" install.py
in the running install path uses a smaller FEATURE_INCLUDES; the "new"
install.py in the source tarball uses the full FEATURE_INCLUDES. After
one --update pass, the omitted entry MUST be deployed — proof the re-exec
into the new code happened.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _build_src_tree(src_root: Path) -> None:
    """Build a complete src tree mirroring the repo layout — full closure."""
    import importlib.util
    import shutil

    spec = importlib.util.spec_from_file_location("install_for_layout", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def _copy_rel(rel: str) -> None:
        # Source-of-truth for install.py is the feature copy, not the deployed
        # root copy (the root copy is a sync artifact that may lag the feature
        # source between IMPLEMENT and SYNC-DEPLOYED).
        if rel == "install.py":
            s = INSTALL_PY
        else:
            s = REPO / rel
        d = src_root / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    for rel in mod.SAME_PATH_FILES:
        _copy_rel(rel)
    for src_rel, _dst_rel in mod.HOOKS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in mod.SKILLS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in mod.AGENTS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in mod.COMMANDS:
        _copy_rel(src_rel)
    for feature, paths in mod.FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        for rel in paths:
            _copy_rel(f"{base}/{rel}")


def _make_old_install_py_with_missing_entry(new_install_py: Path, feature_to_drop: str) -> str:
    """Return the source text of an OLD install.py that omits `feature_to_drop`
    from FEATURE_INCLUDES. We patch the new install.py text by deleting the
    feature's entry from the dict literal — the simplest faithful "old"
    variant. The OLD install.py still self-copies the NEW install.py and
    runs the re-exec branch (so the OLD has the re-exec code too — what
    we're proving is that under the OLD's smaller FEATURE_INCLUDES, the
    dropped entry would never deploy without the re-exec).

    Strategy: locate the f'"{feature_to_drop}": [' line and delete the
    block up through the matching closing ']' + comma. Bracket depth count.
    """
    text = new_install_py.read_text()
    needle = f'"{feature_to_drop}": ['
    start = text.find(needle)
    if start == -1:
        raise RuntimeError(f"feature {feature_to_drop!r} not found in install.py")
    # Walk forward to find the matching closing bracket.
    depth = 0
    i = text.index("[", start)
    while i < len(text):
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    else:
        raise RuntimeError("unbalanced brackets")
    # Include trailing comma + newline if present.
    while end < len(text) and text[end] in ",\n ":
        end += 1
    return text[:start] + text[end:]


def test_update_reexec_picks_up_new_closure_entry():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()

        # 1. Build a "new" source tree (full upstream content).
        new_src = td_path / "new_src"
        new_src.mkdir()
        _build_src_tree(new_src)

        # 2. Build a fresh install at <tmp>/dst using the new source.
        dst = td_path / "dst"
        rc = subprocess.run(
            [sys.executable, str(INSTALL_PY), "--src", str(new_src), "--target", str(dst)],
            capture_output=True, text=True,
        ).returncode
        assert rc == 0, "fresh install failed"

        # 3. Pick a feature shipped via FEATURE_INCLUDES to "drop" from the OLD.
        #    Use 'rabbit-decompose' — small and clearly attributable.
        drop = "rabbit-decompose"
        # Sanity: the new install.py + dst install.py should reference it.
        assert drop in (dst / "install.py").read_text()
        assert (dst / f".claude/features/{drop}/feature.json").is_file()

        # 4. Overwrite the deployed install.py with the OLD variant (missing
        #    the dropped feature). Also remove the deployed feature dir to
        #    prove the re-exec re-deploys it from the new dict.
        old_text = _make_old_install_py_with_missing_entry(new_src / "install.py", drop)
        (dst / "install.py").write_text(old_text)
        import shutil as _sh
        _sh.rmtree(dst / f".claude/features/{drop}")
        assert not (dst / f".claude/features/{drop}/feature.json").is_file()
        # Sanity: the OLD install.py text does NOT mention the dropped feature
        # in its FEATURE_INCLUDES dict (it's removed from the dict literal).
        assert f'"{drop}": [' not in old_text

        # 5. Run the OLD install.py via --update --src=new_src.
        #    The OLD code under test has the re-exec branch but its in-memory
        #    FEATURE_INCLUDES omits the dropped feature. After the SAME_PATH
        #    copy puts the NEW install.py on disk, the re-exec MUST happen
        #    (--src is explicit here, but Inv 22h skip-condition (i) is
        #    explicitly opt-out — we want the re-exec to fire, so we DON'T
        #    pass --src; instead we override the self-fetch via monkey).
        #
        #    Re-approach: invoke without --src to force the self-fetch path
        #    AND monkey-patch fetch_upstream to return new_src. That is the
        #    real-world bug shape (#297) — user runs `install.py --update`
        #    without --src.
        #
        #    We use a small shim script that imports the OLD install.py,
        #    monkey-patches fetch_upstream, then calls main(['install.py',
        #    '--update', '--target', dst]). After re-exec the NEW install.py
        #    runs in a fresh interpreter; for that one we ALSO need
        #    fetch_upstream patched — so set RABBIT_INSTALL_REEXEC_DONE=1
        #    after the first fetch to skip re-exec the second time? No —
        #    we want the re-exec to happen and the second pass to use the
        #    same already-fetched dir. Simplest: write the shim so the
        #    monkey-patched fetch_upstream is in the OLD process; the NEW
        #    process started by os.execv will run unmonkeyed. To avoid the
        #    real network call in the new process, we route the NEW
        #    process through the same --src too: pass --src to the OLD,
        #    and remove Inv 22h skip-condition (i) constraint by setting
        #    a custom env signal? That breaks the spec.
        #
        #    Cleaner approach: run a shim that imports the OLD install.py
        #    module and DIRECTLY calls os.execv simulation — too hacky.
        #
        #    Best: use --src on BOTH old + new and rely on the test asserting
        #    that without re-exec, the dropped feature would not deploy. But
        #    skip-condition (i) says explicit --src disables re-exec... so
        #    use NO --src and patch fetch_upstream BOTH times.
        #
        #    The cleanest test: set RABBIT_REPO/RABBIT_REF to a value that
        #    points fetch_upstream at a local file:// path. But fetch_upstream
        #    uses urllib.request which honors file://, AND tarfile to extract.
        #    We can build a tarball of new_src and serve it via file://.

        # 5a. Build a tarball of new_src.
        import tarfile
        tarball_dir = td_path / "tarball"
        tarball_dir.mkdir()
        # Layout must yield a single top-level "rabbit-workflow-<ref>" dir
        # since fetch_upstream looks for that prefix.
        ref = "fakeref"
        with tarfile.open(tarball_dir / f"{ref}.tar.gz", "w:gz") as tar:
            tar.add(str(new_src), arcname=f"rabbit-workflow-{ref}")

        # 5b. Serve via file:// by overriding RABBIT_REPO to a path-like value
        #     that yields the file URL.
        #     fetch_upstream builds: https://github.com/{repo}/archive/{ref}.tar.gz
        #     We can't change the scheme via env; instead, run a shim that
        #     monkey-patches fetch_upstream at module level before calling main.
        shim = td_path / "shim.py"
        shim.write_text(
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('install', {str(dst / 'install.py')!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "from pathlib import Path\n"
            f"FIXTURE = Path({str(new_src)!r})\n"
            "_orig = mod.fetch_upstream\n"
            "def fake_fetch(repo, ref, dest):\n"
            "    return FIXTURE\n"
            "mod.fetch_upstream = fake_fetch\n"
            f"sys.argv = ['install.py', '--update', '--target', {str(dst)!r}]\n"
            "sys.exit(mod.main())\n"
        )

        env = os.environ.copy()
        env.pop("RABBIT_INSTALL_REEXEC_DONE", None)

        # 6. Run the shim. The OLD install.py runs; after it copies the NEW
        #    install.py to dst, it MUST os.execv into the new one. The NEW
        #    install.py runs without the monkey-patch but ALSO without --src,
        #    so it would attempt a real fetch — BUT the new process inherits
        #    RABBIT_INSTALL_REEXEC_DONE=1, so it skips the re-exec branch.
        #    However, the new process still hits the self-fetch path because
        #    --src is still missing. To work around that, we pre-stage the
        #    monkey-patch via env var: re-exec target is the new install.py,
        #    so the cleanest path is to inject --src into sys.argv as part
        #    of the re-exec? The spec says argv is preserved verbatim.
        #
        #    Alternative: have the shim, BEFORE running, hot-patch BOTH the
        #    OLD install.py file on disk (already done) AND the NEW
        #    install.py (the one in new_src + the one that will land at
        #    dst/install.py after copy) to inject a fetch_upstream override.
        #    Too invasive.
        #
        #    Pragmatic fix: monkey-patch fetch_upstream by replacing its
        #    body in the new_src/install.py FILE before the test runs, so
        #    when the OLD copies the NEW to disk and re-execs into it, the
        #    NEW also has the monkeyed body. We replace fetch_upstream with
        #    a one-line stub that returns FIXTURE path.

        # Patch the new install.py's fetch_upstream to return FIXTURE.
        new_install_text = (new_src / "install.py").read_text()
        # Insert a hot-override at the top of fetch_upstream's body.
        marker = 'def fetch_upstream(repo: str, ref: str, dest: Path) -> Path:'
        if marker in new_install_text:
            override = (
                marker + '\n'
                '    from pathlib import Path as _P\n'
                f'    return _P({str(new_src)!r})\n'
                '    # original body suppressed for test'
            )
            new_install_text = new_install_text.replace(marker, override, 1)
            (new_src / "install.py").write_text(new_install_text)
        # Same patch for the deployed copy at dst/install.py (the OLD).
        old_text2 = (dst / "install.py").read_text()
        if marker in old_text2:
            override2 = (
                marker + '\n'
                '    from pathlib import Path as _P\n'
                f'    return _P({str(new_src)!r})\n'
                '    # original body suppressed for test'
            )
            old_text2 = old_text2.replace(marker, override2, 1)
            (dst / "install.py").write_text(old_text2)

        # Rewrite the shim — no longer needs to monkey-patch in-Python.
        shim.write_text(
            "import sys\n"
            "import importlib.util\n"
            f"spec = importlib.util.spec_from_file_location('install', {str(dst / 'install.py')!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            f"sys.argv = ['install.py', '--update', '--target', {str(dst)!r}]\n"
            "sys.exit(mod.main())\n"
        )

        result = subprocess.run(
            [sys.executable, str(shim)],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, (
            f"--update failed: rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # 7. The dropped feature MUST be deployed — proof the re-exec into
        #    the NEW (full-FEATURE_INCLUDES) install.py happened.
        deployed = dst / f".claude/features/{drop}/feature.json"
        assert deployed.is_file(), (
            f"feature {drop!r} NOT deployed after --update; re-exec did not "
            f"pick up the new FEATURE_INCLUDES.\nstderr: {result.stderr}"
        )

        # 8. stderr should contain the re-exec announcement line.
        assert "re-execing into" in result.stderr, (
            f"missing 're-execing into' stderr line; got: {result.stderr}"
        )

    print("PASS test_update_reexec_picks_up_new_closure_entry")


def main() -> int:
    test_update_reexec_picks_up_new_closure_entry()
    return 0


if __name__ == "__main__":
    sys.exit(main())
