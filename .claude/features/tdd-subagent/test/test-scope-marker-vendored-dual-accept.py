#!/usr/bin/env python3
"""tdd-step.py `_scope_marker_path_for_abort` dual-accepts the vendored mode value.

Issue #1121: `_scope_marker_path_for_abort` read the `.runtime/mode` marker and
compared it with a raw `== "plugin"`. After the canonical vendored-mode value
was renamed from `"plugin"` to `"vendored"`, a `vendored` marker made that
comparison FALSE, so the function fell through to the STANDALONE marker path
(`<repo_root>/.rabbit-scope-active-<feature>`) instead of the vendored path
(`<repo_root>/.runtime/scope-active-<feature>`). scope-guard then could not
find the marker and default-deny protection broke during the TDD cycle in
vendored installs.

Fix: dual-accept BOTH `"vendored"` and the legacy `"plugin"` during the
coexistence window, mirroring dispatch-tdd-subagent.py / scope-guard's
`_VENDORED_MODES = ("vendored", "plugin")`.

END-TO-END: imports tdd-step.py as a module from its SOURCE location, lays
down a real on-disk `.runtime/mode` marker in a temp repo root, and asserts
the resolved scope-marker path for the `vendored`, legacy `plugin`, and
standalone cases. The probe runs in a subprocess so the module's contract
import resolves against the live repo.
"""
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TDD_STEP = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


# Subprocess body: import tdd-step.py as a module, resolve the marker path for
# the given repo root, and print it. Repo root is passed via argv so the
# function under test is exercised directly (no git toplevel resolution).
_PROBE = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('tdd_step_probe', %r)\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(m)\n"
    "root = sys.argv[1]\n"
    "print('MARKER=' + m._scope_marker_path_for_abort(root, 'tdd-subagent'))\n"
)


def _resolve(root):
    res = subprocess.run(
        [sys.executable, "-c", _PROBE % TDD_STEP, root],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None, res.stderr
    for line in res.stdout.splitlines():
        if line.startswith("MARKER="):
            return line.split("=", 1)[1], res.stderr
    return None, res.stderr


def _write_mode(root, value):
    runtime = os.path.join(root, ".runtime")
    os.makedirs(runtime, exist_ok=True)
    with open(os.path.join(runtime, "mode"), "w") as f:
        f.write(value + "\n")


def main():
    feat = "tdd-subagent"

    # Case 1 (the bug): vendored marker -> vendored path, NOT standalone.
    with tempfile.TemporaryDirectory() as tmp:
        _write_mode(tmp, "vendored")
        marker, err = _resolve(tmp)
        expected = os.path.join(tmp, ".runtime", f"scope-active-{feat}")
        standalone = os.path.join(tmp, f".rabbit-scope-active-{feat}")
        if marker is None:
            ko(f"vendored: probe failed: {err!r}")
        elif marker == expected:
            ok("#1121: vendored marker -> vendored scope-marker path")
        elif marker == standalone:
            ko("#1121: vendored marker WRONGLY fell through to standalone path "
               f"({marker})")
        else:
            ko(f"vendored: unexpected path {marker!r}")

    # Case 2 (legacy): plugin marker still resolves to the vendored path.
    with tempfile.TemporaryDirectory() as tmp:
        _write_mode(tmp, "plugin")
        marker, err = _resolve(tmp)
        expected = os.path.join(tmp, ".runtime", f"scope-active-{feat}")
        if marker == expected:
            ok("legacy plugin marker -> vendored scope-marker path (dual-accept)")
        else:
            ko(f"plugin: expected {expected!r}, got {marker!r} (err={err!r})")

    # Case 3 (standalone regression): explicit 'standalone' marker -> repo-root
    # dashed marker, behavior unchanged.
    with tempfile.TemporaryDirectory() as tmp:
        _write_mode(tmp, "standalone")
        marker, err = _resolve(tmp)
        expected = os.path.join(tmp, f".rabbit-scope-active-{feat}")
        if marker == expected:
            ok("standalone marker -> repo-root dashed scope-marker path")
        else:
            ko(f"standalone: expected {expected!r}, got {marker!r} (err={err!r})")

    # Case 4 (standalone regression): no marker at all -> repo-root dashed path.
    with tempfile.TemporaryDirectory() as tmp:
        marker, err = _resolve(tmp)
        expected = os.path.join(tmp, f".rabbit-scope-active-{feat}")
        if marker == expected:
            ok("no marker -> repo-root dashed scope-marker path (standalone)")
        else:
            ko(f"no-marker: expected {expected!r}, got {marker!r} (err={err!r})")


print(f"running scope-marker vendored dual-accept tests against {TDD_STEP}")
main()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
