#!/usr/bin/env python3
"""test-mode-value-dual-accept.py — Inv 49 e2e.

Every rabbit-cage site that branches on the vendored-mode value (the string
`detect_mode` returns and `write_mode_marker` writes into
`<repo_root>/.rabbit/.runtime/mode`) MUST DUAL-ACCEPT both the legacy `"plugin"`
spelling and the new `"vendored"` spelling, so the gate stays green both before
and after rabbit-meta flips the canonical value. rabbit-cage NEVER writes the
value and NEVER changes `detect_mode`; it only reads/compares.

This drives the REAL deployed scripts as subprocesses:

  t1/t2: `hooks/scope-guard.py` vendored-branch dispatch — a Write to
         `.rabbit/.claude/**` takes the vendored-branch always-DENY (whose
         message names rabbit's own machinery) for BOTH marker values; the
         vendored carve-out `.rabbit/CLAUDE.md` ALLOWs for BOTH.
  t3/t4: `scripts/scope-guard-on.py` per-mode override-marker path — with the
         marker holding each value, the override file at the vendored path
         `<repo_root>/.rabbit/.rabbit-scope-override` is the one it revokes.
  t5/t6: `scripts/show-mode.py` derives the PARENT-of-`.rabbit` project_root
         (the vendored branch) for BOTH `detect_mode` values, simulated by a
         stub mode_detection lib returning each value.

Non-interactive. Exits non-zero on failure.
"""
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CAGE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

SCOPE_GUARD = os.path.join(CAGE_DIR, "hooks", "scope-guard.py")
SCOPE_GUARD_ON = os.path.join(CAGE_DIR, "scripts", "scope-guard-on.py")
SHOW_MODE = os.path.join(CAGE_DIR, "scripts", "show-mode.py")

RUNTIME_DIR = os.path.join(REPO_ROOT, ".rabbit", ".runtime")
MODE_FILE = os.path.join(RUNTIME_DIR, "mode")

MODE_VALUES = ("plugin", "vendored")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


@contextlib.contextmanager
def saved_mode_marker():
    """Snapshot/restore the real repo's .rabbit/.runtime/mode file."""
    saved = None
    if os.path.isfile(MODE_FILE):
        with open(MODE_FILE, "rb") as f:
            saved = f.read()
    try:
        yield
    finally:
        if os.path.isfile(MODE_FILE):
            os.remove(MODE_FILE)
        if saved is not None:
            os.makedirs(RUNTIME_DIR, exist_ok=True)
            with open(MODE_FILE, "wb") as f:
                f.write(saved)


def write_mode(value):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(MODE_FILE, "w") as f:
        f.write(value)


def run_guard(target_path):
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": target_path, "content": "x"}}
    res = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload), capture_output=True, text=True,
    )
    return res.returncode, res.stderr


print("test-mode-value-dual-accept.py")
print()

# --- t1/t2: scope-guard.py vendored-branch dispatch for both values --------
for value in MODE_VALUES:
    with saved_mode_marker():
        write_mode(value)
        # The vendored branch ALWAYS-DENYs .rabbit/.claude/** with a message
        # naming rabbit's own machinery — a branch-specific signal proving the
        # value comparison routed into plugin_decide().
        target = os.path.join(REPO_ROOT, ".rabbit", ".claude",
                              "__dual_accept_probe__.py")
        rc, stderr = run_guard(target)
        name = f"scope-guard[{value}]"
        if rc == 2 and "rabbit's own machinery" in stderr:
            ok(name, "vendored-branch always-DENY of .rabbit/.claude/** fired")
        else:
            fail(name, f".rabbit/.claude/** not denied by vendored branch: "
                       f"rc={rc} stderr={stderr!r}")
        # The vendored carve-out .rabbit/CLAUDE.md ALLOWs in the same branch.
        carve = os.path.join(REPO_ROOT, ".rabbit", "CLAUDE.md")
        rc2, stderr2 = run_guard(carve)
        if rc2 == 0:
            ok(name, "vendored carve-out .rabbit/CLAUDE.md ALLOWED")
        else:
            fail(name, f"carve-out not allowed: rc={rc2} stderr={stderr2!r}")


# --- t3/t4: scope-guard-on.py per-mode override path for both values -------
for value in MODE_VALUES:
    with tempfile.TemporaryDirectory() as tmp:
        # Simulate a host project: <tmp>/proj with a .rabbit/ install dir.
        proj = os.path.join(tmp, "proj")
        rabbit = os.path.join(proj, ".rabbit")
        runtime = os.path.join(rabbit, ".runtime")
        os.makedirs(runtime)
        with open(os.path.join(runtime, "mode"), "w") as f:
            f.write(value)
        # The vendored override marker lives at <repo_root>/.rabbit/.rabbit-scope-override
        override = os.path.join(rabbit, ".rabbit-scope-override")
        with open(override, "w") as f:
            f.write("session")
        env = dict(os.environ)
        env["RABBIT_ROOT"] = proj
        res = subprocess.run(
            [sys.executable, SCOPE_GUARD_ON],
            capture_output=True, text=True, env=env,
        )
        name = f"scope-guard-on[{value}]"
        if res.returncode != 0:
            fail(name, f"exit {res.returncode}; stderr={res.stderr!r}")
        elif os.path.exists(override):
            fail(name, "vendored override marker NOT revoked (path dual-accept "
                       "failed for this value)")
        else:
            ok(name, "revoked override at vendored path .rabbit/.rabbit-scope-override")


# --- t5/t6: show-mode.py vendored project-root branch for both values ------
def _build_show_mode_tree(install_root, detect_returns):
    """Lay down show-mode.py + a STUB mode_detection lib that returns a fixed
    value, mirroring the layout show-mode.py resolves against."""
    cage_scripts = os.path.join(
        install_root, ".claude", "features", "rabbit-cage", "scripts")
    meta_lib = os.path.join(
        install_root, ".claude", "features", "rabbit-meta", "lib")
    os.makedirs(cage_scripts)
    os.makedirs(meta_lib)
    dst = os.path.join(cage_scripts, "show-mode.py")
    shutil.copy(SHOW_MODE, dst)
    with open(os.path.join(meta_lib, "mode_detection.py"), "w") as f:
        f.write("def detect_mode(cwd):\n    return %r\n" % detect_returns)
    return dst


for value in MODE_VALUES:
    with tempfile.TemporaryDirectory() as tmp:
        project = os.path.join(tmp, "host-project")
        rabbit = os.path.join(project, ".rabbit")
        os.makedirs(project)
        script = _build_show_mode_tree(rabbit, value)
        env = dict(os.environ)
        env["RABBIT_ROOT"] = rabbit
        res = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, cwd=rabbit, env=env,
        )
        name = f"show-mode[{value}]"
        obj = None
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    obj = None
                if obj is not None:
                    break
        if res.returncode != 0 or obj is None:
            fail(name, f"exit {res.returncode}; stdout={res.stdout!r}")
        elif obj.get("mode") != value:
            fail(name, f"mode not passed through: got {obj.get('mode')!r}")
        elif obj.get("project_root") != project:
            # Vendored branch: project_root MUST be the PARENT of .rabbit.
            fail(name, f"vendored project-root branch did not fire: "
                       f"project_root={obj.get('project_root')!r} "
                       f"expected {project!r}")
        else:
            ok(name, "vendored project-root branch (parent of .rabbit) fired")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    print("test-mode-value-dual-accept: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mode-value-dual-accept: all checks passed.")
sys.exit(0)
