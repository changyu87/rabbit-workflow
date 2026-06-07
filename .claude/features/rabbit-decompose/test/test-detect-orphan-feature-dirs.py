#!/usr/bin/env python3
"""test-detect-orphan-feature-dirs.py — orphan feature-dir detection guard
(#1040).

End-to-end test of rabbit-decompose's pre-Step-2 detection of an INCONSISTENT
project state: feature directories exist on disk under the resolved `features/`
root, but they are NOT represented in `project-map.json` (or `project-map.json`
is entirely ABSENT while dirs exist). This is the state a partial/aborted
decompose leaves behind, and before #1040 `--detect-existing` did not surface
it at all — so `handoff-scaffold.py --features <accepted.json>` failed at
scaffold time ("scaffold target .../features/<name> already exists") with no
recovery path.

The fix extends `--detect-existing` to SCAN the resolved `features/` root (the
sibling `features/` dir next to `project-map.json`, where scaffold-feature.py
writes each feature dir), diff the on-disk dirs against the project-map's
`features` map (treating an absent map as empty), and SURFACE:

  - `feature_dirs_on_disk`: sorted names of dirs present under `features/`,
  - `orphan_feature_dirs`: sorted names present on disk but ABSENT from the
    project-map's `features` map (including the absent-map case where every
    on-disk dir is an orphan).

This is DETECTION + SURFACING only — no auto-delete, no auto-adopt. The
adopt-vs-proceed decision stays the caller's.

This test asserts, end-to-end:

  1. Dirs on disk but NO project-map.json -> every on-disk dir is surfaced as
     an orphan; `feature_dirs_on_disk` enumerates them; `existing` stays false
     (no map features) so first-run propose flow is unchanged.
  2. Dirs on disk PARTIALLY represented in project-map.json -> only the dirs
     absent from the map are orphans; mapped dirs are not.
  3. Map features fully matching on-disk dirs -> no orphans (clean state).
  4. No features/ dir at all -> empty lists, no crash.
  5. Mode-driven: standalone resolves features/ under
     `.rabbit/rabbit-project/features/`.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when existing-decomposition detection is provided
    natively by the rabbit CLI, retiring the companion handoff-scaffold.py
    detector.
"""
import json
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "handoff-scaffold.py")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _run_detect(rabbit_root, workdir):
    argv = [sys.executable, SCRIPT, "--detect-existing",
            "--rabbit-root", rabbit_root]
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=workdir)
    if proc.returncode != 0:
        fail(f"handoff-scaffold.py --detect-existing exited "
             f"{proc.returncode}; stderr:\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"--detect-existing did not emit JSON: {e}; "
             f"stdout:\n{proc.stdout}")


def _write_project_map(rabbit_project_dir, features):
    os.makedirs(rabbit_project_dir, exist_ok=True)
    pmap = {"schema_version": "1.0.0", "features": features}
    path = os.path.join(rabbit_project_dir, "project-map.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pmap, f)
    return path


def _make_feature_dirs(rabbit_project_dir, names):
    feats_root = os.path.join(rabbit_project_dir, "features")
    for n in names:
        os.makedirs(os.path.join(feats_root, n), exist_ok=True)
    # a stray file at the features/ root must NOT be treated as a feature dir
    open(os.path.join(feats_root, ".keep"), "w").close()
    return feats_root


def _make_plugin_tree(parent):
    host = os.path.join(parent, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    os.makedirs(rabbit_root)
    return rabbit_root


def _make_standalone_tree(parent):
    root = os.path.join(parent, "standalone-root")
    os.makedirs(root)
    return root


if not os.path.isfile(SCRIPT):
    fail(f"missing orchestrator script: {SCRIPT}")


# --- Check 1: dirs on disk, NO project-map.json -> all are orphans -----------
with tempfile.TemporaryDirectory() as td:
    rabbit_root = _make_plugin_tree(td)
    rp = os.path.join(rabbit_root, "rabbit-project")
    _make_feature_dirs(rp, ["alpha-feature", "beta-feature"])
    res = _run_detect(rabbit_root, td)
    on_disk = set(res.get("feature_dirs_on_disk") or [])
    if on_disk != {"alpha-feature", "beta-feature"}:
        fail("absent-map: feature_dirs_on_disk must enumerate every dir under "
             f"features/ (ignoring stray files); got {on_disk!r}")
    orphans = set(res.get("orphan_feature_dirs") or [])
    if orphans != {"alpha-feature", "beta-feature"}:
        fail("absent-map: with no project-map.json every on-disk dir is an "
             f"orphan; got {orphans!r}")
    if res.get("existing") is not False:
        fail("absent-map: existing must stay False when the map has no "
             f"features; got {res.get('existing')!r}")

# --- Check 2: dirs partially represented in project-map -> only absent ones --
with tempfile.TemporaryDirectory() as td2:
    rabbit_root = _make_plugin_tree(td2)
    rp = os.path.join(rabbit_root, "rabbit-project")
    _write_project_map(rp, {
        "alpha-feature": {"paths": ["src/alpha/**"],
                          "feature_dir": "rabbit-project/features/alpha-feature"},
    })
    _make_feature_dirs(rp, ["alpha-feature", "beta-feature", "gamma-feature"])
    res = _run_detect(rabbit_root, td2)
    on_disk = set(res.get("feature_dirs_on_disk") or [])
    if on_disk != {"alpha-feature", "beta-feature", "gamma-feature"}:
        fail(f"partial-map: feature_dirs_on_disk wrong; got {on_disk!r}")
    orphans = set(res.get("orphan_feature_dirs") or [])
    if orphans != {"beta-feature", "gamma-feature"}:
        fail("partial-map: only dirs ABSENT from the project-map are orphans; "
             f"got {orphans!r}")

# --- Check 3: map fully matches on-disk dirs -> no orphans (clean) -----------
with tempfile.TemporaryDirectory() as td3:
    rabbit_root = _make_plugin_tree(td3)
    rp = os.path.join(rabbit_root, "rabbit-project")
    _write_project_map(rp, {
        "alpha-feature": {"paths": ["src/alpha/**"],
                          "feature_dir": "rabbit-project/features/alpha-feature"},
        "beta-feature": {"paths": ["src/beta/**"],
                         "feature_dir": "rabbit-project/features/beta-feature"},
    })
    _make_feature_dirs(rp, ["alpha-feature", "beta-feature"])
    res = _run_detect(rabbit_root, td3)
    orphans = set(res.get("orphan_feature_dirs") or [])
    if orphans:
        fail(f"clean state: no orphans expected; got {orphans!r}")
    on_disk = set(res.get("feature_dirs_on_disk") or [])
    if on_disk != {"alpha-feature", "beta-feature"}:
        fail(f"clean state: feature_dirs_on_disk wrong; got {on_disk!r}")

# --- Check 4: no features/ dir at all -> empty lists, no crash ---------------
with tempfile.TemporaryDirectory() as td4:
    rabbit_root = _make_plugin_tree(td4)
    res = _run_detect(rabbit_root, td4)
    if res.get("feature_dirs_on_disk") != []:
        fail("no features/ dir: feature_dirs_on_disk must be []; got "
             f"{res.get('feature_dirs_on_disk')!r}")
    if res.get("orphan_feature_dirs") != []:
        fail("no features/ dir: orphan_feature_dirs must be []; got "
             f"{res.get('orphan_feature_dirs')!r}")

# --- Check 5: mode-driven features/ root (standalone) ------------------------
with tempfile.TemporaryDirectory() as td5:
    root = _make_standalone_tree(td5)
    rp = os.path.join(root, ".rabbit", "rabbit-project")
    _make_feature_dirs(rp, ["alpha-feature"])
    res = _run_detect(root, td5)
    if res.get("mode") != "standalone":
        fail(f"standalone: expected mode 'standalone'; got {res.get('mode')!r}")
    orphans = set(res.get("orphan_feature_dirs") or [])
    if orphans != {"alpha-feature"}:
        fail("standalone: features/ under .rabbit/rabbit-project must be "
             f"scanned; got orphans {orphans!r}")

print("All checks passed.")
