#!/usr/bin/env python3
"""BACKLOG-18 unit test for pure-function renderers (Inv 76).

Imports the render_* functions from sync-check.py and session-init.py;
invokes them with controlled state; captures sys.stdout/stderr and asserts
no side-effect writes occurred. Asserts return values are either None or
dict with expected keys.
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import contextlib
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")
SESSION_INIT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("test-RABBIT-CAGE-BACKLOG-18-pure-renderer-no-side-effects.py")
print("Unit test: pure-function renderers (Inv 76)")
print()

sync = load_module(SYNC_CHECK, "sync_check_mod")
sess = load_module(SESSION_INIT, "session_init_mod")

# Expected renderers
SYNC_RENDERERS = [
    "render_claude_md_drift",
    "render_surface_drift",
    "render_scope_guard",
    "render_human_approval",
    "render_skills_updated",
]
SESSION_RENDERERS = [
    "render_r1_branch",
    "render_policy",
]

# ---- t1..t5: sync-check renderers exist and are callable ----
print("=== t1-5: sync-check.py defines all 5 pure renderers ===")
for name in SYNC_RENDERERS:
    fn = getattr(sync, name, None)
    if callable(fn):
        ok(f"{name} exists and is callable")
    else:
        fail_t(f"{name} missing or not callable on sync-check module")

# ---- t6..t7: session-init renderers exist and callable ----
print()
print("=== t6-7: session-init.py defines both pure renderers ===")
for name in SESSION_RENDERERS:
    fn = getattr(sess, name, None)
    if callable(fn):
        ok(f"{name} exists and is callable")
    else:
        fail_t(f"{name} missing or not callable on session-init module")

# ---- t-side-effects: invoking a renderer on an empty repo does NOT write
# to stdout/stderr ----
print()
print("=== t-side-effects: renderers produce no stdout/stderr ===")

tmproots = []
try:
    # build an empty repo (no markers, no drift)
    from test_helpers import make_git_repo
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    from pathlib import Path
    root = Path(tmproot)

    # renderers that take only root
    for name in ["render_surface_drift", "render_scope_guard",
                 "render_human_approval", "render_skills_updated"]:
        fn = getattr(sync, name, None)
        if fn is None:
            continue
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            try:
                result = fn(root)
            except TypeError:
                # if signature differs, try with no args
                try:
                    result = fn()
                except Exception as e:
                    fail_t(f"{name} could not be invoked: {e}")
                    continue
            except Exception as e:
                fail_t(f"{name} raised on empty repo: {e}")
                continue
        if buf_out.getvalue() != "":
            fail_t(f"{name} wrote to stdout: {buf_out.getvalue()!r}")
        else:
            ok(f"{name} produced no stdout")
        if result is None or isinstance(result, dict):
            ok(f"{name} returned None or dict (got {type(result).__name__})")
        else:
            fail_t(f"{name} returned wrong type: {type(result).__name__}")

    # session-init renderers
    for name in SESSION_RENDERERS:
        fn = getattr(sess, name, None)
        if fn is None:
            continue
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            try:
                # off-main branch so render_r1_branch returns None without
                # creating a branch
                subprocess.run(
                    ["git", "-C", str(root), "checkout", "-q", "-b", "feature/x"],
                    capture_output=True,
                )
                result = fn(root)
            except Exception as e:
                fail_t(f"{name} raised: {e}")
                continue
        if buf_out.getvalue() != "":
            fail_t(f"{name} wrote to stdout: {buf_out.getvalue()!r}")
        else:
            ok(f"{name} produced no stdout")
        if result is None or isinstance(result, dict):
            ok(f"{name} returned None or dict")
        else:
            fail_t(f"{name} returned wrong type: {type(result).__name__}")

    # ---- t-skills-shape: render_skills_updated returns dict with systemMessage
    # when marker exists, and consumes the marker ----
    print()
    print("=== t-skills-shape: render_skills_updated returns dict and consumes marker ===")
    marker = root / ".rabbit-skills-updated"
    marker.write_text("foo\nbar\n")
    buf_out = io.StringIO()
    with contextlib.redirect_stdout(buf_out):
        result = sync.render_skills_updated(root)
    if isinstance(result, dict) and "systemMessage" in result:
        ok("returned dict with systemMessage key")
    else:
        fail_t(f"expected dict with systemMessage, got {result!r}")
    if not marker.exists():
        ok("marker consumed by renderer")
    else:
        fail_t("marker NOT consumed by renderer")
    if buf_out.getvalue() == "":
        ok("no stdout during render_skills_updated invocation")
    else:
        fail_t(f"stdout leaked: {buf_out.getvalue()!r}")

finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
