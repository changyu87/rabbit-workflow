#!/usr/bin/env python3
"""test-runtime-write-mode-marker.py — exercises write_mode_marker:
lazy-imports rabbit-meta.lib.mode_detection.detect_mode, calls
detect_mode(os.getcwd()), ensures <repo_root>/.rabbit/.runtime/ exists,
writes the resulting "plugin" or "standalone" string to
<repo_root>/.rabbit/.runtime/mode. Returns ok_result on success,
error_result on ImportError or OSError. Idempotent (content-equality).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import write_mode_marker  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _chdir_and_call(target_cwd, **kwargs):
    """Call write_mode_marker with cwd set to target_cwd, restore cwd after."""
    saved = os.getcwd()
    try:
        os.chdir(target_cwd)
        return write_mode_marker(**kwargs)
    finally:
        os.chdir(saved)


# t1: plugin mode — cwd is .rabbit/ inside a host project tree -> "plugin"
with tempfile.TemporaryDirectory() as td:
    rabbit_dir = os.path.join(td, ".rabbit")
    os.makedirs(rabbit_dir)
    # sibling to .rabbit/ so detect_mode sees a host-project sibling
    os.makedirs(os.path.join(td, "src"))
    r = _chdir_and_call(rabbit_dir, repo_root=td)
    mode_path = os.path.join(td, ".rabbit", ".runtime", "mode")
    if r != {"type": "ok"}:
        fail(f"t1: expected ok_result, got {r!r}")
    elif not os.path.isfile(mode_path):
        fail(f"t1: mode file not written: {mode_path}")
    else:
        with open(mode_path) as f:
            content = f.read()
        if content == "plugin":
            ok("t1: plugin mode detected, mode file content == 'plugin'")
        else:
            fail(f"t1: expected content 'plugin', got {content!r}")


# t2: standalone mode — cwd is a plain dir, no .rabbit basename
with tempfile.TemporaryDirectory() as td:
    # td itself is not named .rabbit, so detect_mode -> standalone
    r = _chdir_and_call(td, repo_root=td)
    mode_path = os.path.join(td, ".rabbit", ".runtime", "mode")
    if r != {"type": "ok"}:
        fail(f"t2: expected ok_result, got {r!r}")
    elif not os.path.isfile(mode_path):
        fail(f"t2: mode file not written: {mode_path}")
    else:
        with open(mode_path) as f:
            content = f.read()
        if content == "standalone":
            ok("t2: standalone mode detected, mode file content == 'standalone'")
        else:
            fail(f"t2: expected content 'standalone', got {content!r}")


# t3: idempotent — second call with unchanged mode is no-op (mtime preserved)
with tempfile.TemporaryDirectory() as td:
    r1 = _chdir_and_call(td, repo_root=td)
    mode_path = os.path.join(td, ".rabbit", ".runtime", "mode")
    if r1 != {"type": "ok"} or not os.path.isfile(mode_path):
        fail(f"t3: setup fail; r1={r1!r}")
    else:
        mtime1 = os.path.getmtime(mode_path)
        content1 = open(mode_path).read()
        # Force a measurable gap so any rewrite would bump mtime.
        import time as _t
        _t.sleep(0.05)
        r2 = _chdir_and_call(td, repo_root=td)
        mtime2 = os.path.getmtime(mode_path)
        content2 = open(mode_path).read()
        if r2 != {"type": "ok"}:
            fail(f"t3: second call returned {r2!r}")
        elif content2 != content1:
            fail(f"t3: content changed: {content1!r} -> {content2!r}")
        elif mtime2 != mtime1:
            fail(f"t3: mtime changed (non-idempotent write): {mtime1} -> {mtime2}")
        else:
            ok("t3: idempotent — second call did not rewrite mode file")


# t4: ImportError handling — block rabbit-meta resolution and assert error_result.
# We block by pointing repo_root at a tmpdir that has NO .claude/features/rabbit-meta,
# AND by ensuring no leftover sys.modules entry can satisfy the import.
with tempfile.TemporaryDirectory() as td:
    # repo_root without rabbit-meta installed under .claude/features/rabbit-meta
    # The function should fail to load detect_mode and return error_result.
    saved_mod = sys.modules.pop("rabbit_meta_mode_detection", None)
    try:
        r = _chdir_and_call(td, repo_root=td)
    finally:
        if saved_mod is not None:
            sys.modules["rabbit_meta_mode_detection"] = saved_mod
    if isinstance(r, dict) and r.get("type") == "error" and "rabbit-meta unavailable" in r.get("message", ""):
        ok("t4: rabbit-meta missing -> error_result('rabbit-meta unavailable')")
    else:
        fail(f"t4: expected error_result mentioning 'rabbit-meta unavailable', got {r!r}")


# t5: directory creation — fresh tmpdir with no .rabbit/.runtime/ -> dir is created
with tempfile.TemporaryDirectory() as td:
    runtime_dir = os.path.join(td, ".rabbit", ".runtime")
    if os.path.isdir(runtime_dir):
        fail("t5: setup invariant violated — runtime_dir exists pre-call")
    else:
        r = _chdir_and_call(td, repo_root=td)
        mode_path = os.path.join(runtime_dir, "mode")
        if r != {"type": "ok"}:
            fail(f"t5: expected ok_result, got {r!r}")
        elif not os.path.isdir(runtime_dir):
            fail(f"t5: runtime dir not created: {runtime_dir}")
        elif not os.path.isfile(mode_path):
            fail(f"t5: mode file not created: {mode_path}")
        else:
            ok("t5: .rabbit/.runtime/ dir + mode file created on first call")


if FAIL:
    print("test-runtime-write-mode-marker: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-write-mode-marker: all checks passed.")
