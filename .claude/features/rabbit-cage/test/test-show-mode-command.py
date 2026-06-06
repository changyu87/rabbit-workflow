#!/usr/bin/env python3
"""rabbit-cage e2e — scripts/show-mode.py deterministic mode reporter (issue #888).

Drives scripts/show-mode.py as a SUBPROCESS (one invocation, zero AI) and
asserts it:
  t1: emits valid JSON to stdout with a `mode` field and the evidence fields
      (rabbit_root, project_root, feature_dir, evidence{}), exit 0, in a
      simulated VENDORED layout (RABBIT_ROOT points at a `.rabbit` subdir that
      sits inside a larger project) -> mode in ("vendored", "plugin")
      (dual-accept of the in-flight rename, Inv 50).
  t2: same, in a simulated STANDALONE layout (RABBIT_ROOT points at the repo
      root which IS the rabbit install) -> mode == "standalone".
  t3: emits a human-readable one-line summary beginning `Mode: ` alongside the
      JSON (Machine First: machine JSON + derivative human line).
  t4: agrees with the canonical rabbit-meta resolver — re-detecting via
      detect_mode against the same layout yields the same mode string.

The script lazy-imports rabbit-meta.lib.mode_detection.detect_mode relative to
its OWN location (a cross-feature INVOKE, not an edit), so each simulated
layout copies the real rabbit-meta lib + the real show-mode.py into a throwaway
`.claude/features/...` tree and runs the copy.
"""
from __future__ import annotations

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

REAL_SHOW_MODE = os.path.join(CAGE_DIR, "scripts", "show-mode.py")
REAL_META_LIB = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-meta", "lib", "mode_detection.py")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL {t}: {msg}", file=sys.stderr)
    fail_n += 1


def _build_install_tree(install_root: str) -> str:
    """Lay down a minimal `.claude/features` tree under install_root holding
    the real show-mode.py and the real rabbit-meta mode_detection lib, mirroring
    the on-disk layout the script resolves against. Returns the show-mode.py
    path inside the tree."""
    cage_scripts = os.path.join(
        install_root, ".claude", "features", "rabbit-cage", "scripts")
    meta_lib = os.path.join(
        install_root, ".claude", "features", "rabbit-meta", "lib")
    os.makedirs(cage_scripts)
    os.makedirs(meta_lib)
    dst_script = os.path.join(cage_scripts, "show-mode.py")
    shutil.copy(REAL_SHOW_MODE, dst_script)
    shutil.copy(REAL_META_LIB, os.path.join(meta_lib, "mode_detection.py"))
    return dst_script


def _run(script_path: str, rabbit_root: str, cwd: str):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = rabbit_root
    return subprocess.run(
        [sys.executable, script_path],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def _parse_json(stdout: str):
    """The script emits JSON + a human summary line; pull the JSON object out
    by scanning lines for the one that parses as a dict with a `mode` key."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "mode" in obj:
            return obj
    return None


# --- t1: plugin layout ----------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    project = os.path.join(tmp, "host-project")
    rabbit = os.path.join(project, ".rabbit")
    os.makedirs(project)
    os.makedirs(os.path.join(project, "src"))  # sibling content => plugin
    script = _build_install_tree(rabbit)
    res = _run(script, rabbit_root=rabbit, cwd=rabbit)
    obj = _parse_json(res.stdout)
    if res.returncode != 0:
        fail_t("t1", f"exit {res.returncode}; stderr={res.stderr!r}")
    elif obj is None:
        fail_t("t1", f"no JSON with `mode` in stdout: {res.stdout!r}")
    elif obj.get("mode") not in ("vendored", "plugin"):
        # Dual-accept (Inv 50): the canonical vendored-mode value is being
        # renamed from "plugin" to "vendored" by rabbit-meta; accept EITHER so
        # this stays green across the detect_mode flip.
        fail_t("t1", f"expected mode 'vendored' or 'plugin', "
                     f"got {obj.get('mode')!r}")
    else:
        missing = [k for k in ("rabbit_root", "project_root", "feature_dir",
                               "evidence") if k not in obj]
        if missing:
            fail_t("t1", f"missing evidence fields: {missing}")
        elif not isinstance(obj["evidence"], dict):
            fail_t("t1", f"evidence not an object: {obj['evidence']!r}")
        else:
            ok("t1", "plugin layout -> mode 'plugin' with evidence fields, exit 0")

# --- t2: standalone layout ------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    # Standalone: the repo root itself IS the rabbit install (basename not
    # `.rabbit`); RABBIT_ROOT points at it.
    repo = os.path.join(tmp, "rabbit-self")
    os.makedirs(repo)
    os.makedirs(os.path.join(repo, "src"))
    script = _build_install_tree(repo)
    res = _run(script, rabbit_root=repo, cwd=repo)
    obj = _parse_json(res.stdout)
    if res.returncode != 0:
        fail_t("t2", f"exit {res.returncode}; stderr={res.stderr!r}")
    elif obj is None:
        fail_t("t2", f"no JSON with `mode` in stdout: {res.stdout!r}")
    elif obj.get("mode") != "standalone":
        fail_t("t2", f"expected mode 'standalone', got {obj.get('mode')!r}")
    else:
        missing = [k for k in ("rabbit_root", "project_root", "feature_dir",
                               "evidence") if k not in obj]
        if missing:
            fail_t("t2", f"missing evidence fields: {missing}")
        else:
            ok("t2", "standalone layout -> mode 'standalone' with evidence, exit 0")

# --- t3: human-readable summary line --------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    project = os.path.join(tmp, "host-project")
    rabbit = os.path.join(project, ".rabbit")
    os.makedirs(project)
    os.makedirs(os.path.join(project, "src"))
    script = _build_install_tree(rabbit)
    res = _run(script, rabbit_root=rabbit, cwd=rabbit)
    summary_lines = [ln for ln in res.stdout.splitlines()
                     if ln.strip().startswith("Mode:")]
    if res.returncode != 0:
        fail_t("t3", f"exit {res.returncode}; stderr={res.stderr!r}")
    elif not summary_lines:
        fail_t("t3", f"no `Mode: ` human summary line in stdout: {res.stdout!r}")
    elif not any(v in summary_lines[0] for v in ("vendored", "plugin")):
        # Dual-accept (Inv 50): the human summary names the mode verbatim, so it
        # carries EITHER spelling depending on what detect_mode returns.
        fail_t("t3", f"summary line does not name mode: {summary_lines[0]!r}")
    else:
        ok("t3", f"human summary line present: {summary_lines[0].strip()!r}")

# --- t4: agrees with canonical rabbit-meta detect_mode --------------------
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("md_canon", REAL_META_LIB)
md_canon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md_canon)

with tempfile.TemporaryDirectory() as tmp:
    project = os.path.join(tmp, "host-project")
    rabbit = os.path.join(project, ".rabbit")
    os.makedirs(project)
    os.makedirs(os.path.join(project, "src"))
    script = _build_install_tree(rabbit)
    res = _run(script, rabbit_root=rabbit, cwd=rabbit)
    obj = _parse_json(res.stdout)
    canonical = md_canon.detect_mode(rabbit)
    if obj is None:
        fail_t("t4", f"no JSON: {res.stdout!r}")
    elif obj.get("mode") != canonical:
        fail_t("t4", f"show-mode {obj.get('mode')!r} != detect_mode {canonical!r}")
    else:
        ok("t4", f"show-mode agrees with canonical detect_mode ({canonical!r})")

# --- t5: DUAL-ACCEPT of the vendored-mode value (Inv 49) -------------------
# The canonical vendored-mode value is being renamed from "plugin" to
# "vendored" (owned by rabbit-meta). show-mode.py's project-root branch — which
# derives project_root as the PARENT of the .rabbit install dir — MUST fire for
# BOTH values. Drive the script against a STUB detect_mode returning each value.
def _build_stub_tree(install_root, detect_returns):
    cage_scripts = os.path.join(
        install_root, ".claude", "features", "rabbit-cage", "scripts")
    meta_lib = os.path.join(
        install_root, ".claude", "features", "rabbit-meta", "lib")
    os.makedirs(cage_scripts)
    os.makedirs(meta_lib)
    dst = os.path.join(cage_scripts, "show-mode.py")
    shutil.copy(REAL_SHOW_MODE, dst)
    with open(os.path.join(meta_lib, "mode_detection.py"), "w") as f:
        f.write("def detect_mode(cwd):\n    return %r\n" % detect_returns)
    return dst


for value in ("plugin", "vendored"):
    with tempfile.TemporaryDirectory() as tmp:
        project = os.path.join(tmp, "host-project")
        rabbit = os.path.join(project, ".rabbit")
        os.makedirs(project)
        script = _build_stub_tree(rabbit, value)
        res = _run(script, rabbit_root=rabbit, cwd=rabbit)
        obj = _parse_json(res.stdout)
        if res.returncode != 0 or obj is None:
            fail_t("t5", f"[{value}] exit {res.returncode}; stdout={res.stdout!r}")
        elif obj.get("mode") != value:
            fail_t("t5", f"[{value}] mode not passed through: {obj.get('mode')!r}")
        elif obj.get("project_root") != project:
            fail_t("t5", f"[{value}] vendored project-root branch did not fire: "
                         f"project_root={obj.get('project_root')!r} != {project!r}")
        else:
            ok("t5", f"[{value}] vendored project-root branch fires (dual-accept)")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
