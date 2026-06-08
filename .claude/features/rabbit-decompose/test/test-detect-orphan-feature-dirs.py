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
    project-map's `features` map AND not a by-design greenfield dir.

This is DETECTION + SURFACING only — no auto-delete, no auto-adopt. The
adopt-vs-proceed decision stays the caller's.

GREENFIELD EXCLUSION (#1042). A dir on disk but ABSENT from project-map.json is
a TRUE orphan ONLY if its `feature.json` declares NON-EMPTY `paths` — a real
feature that should be registered but isn't. A greenfield feature has
`paths: []` in its `feature.json` BY DESIGN: the project-map schema requires
non-empty paths, so scaffold-feature.py INTENTIONALLY never writes greenfield
features into project-map.json. Such a dir is NOT an orphan and MUST be excluded
from `orphan_feature_dirs`. A dir with NO `feature.json`, or an
unreadable/malformed one, is genuinely inconsistent and IS still surfaced as an
orphan (the safe classification) — but the detector must NOT crash on it.
`feature_dirs_on_disk` (the raw scan) still enumerates ALL dirs; only
`orphan_feature_dirs` gets the greenfield-aware filter.

This test asserts, end-to-end:

  1. Dirs on disk (with NON-EMPTY-paths feature.json) but NO project-map.json
     -> every such dir is surfaced as an orphan; `feature_dirs_on_disk`
     enumerates them; `existing` stays false (no map features) so first-run
     propose flow is unchanged.
  2. Dirs on disk PARTIALLY represented in project-map.json -> only the
     non-greenfield dirs absent from the map are orphans; mapped dirs are not.
  3. Map features fully matching on-disk dirs -> no orphans (clean state).
  4. No features/ dir at all -> empty lists, no crash.
  5. Mode-driven: standalone resolves features/ under
     `.rabbit/rabbit-project/features/`.
  6. Greenfield exclusion: a dir whose feature.json has `paths: []` is absent
     from the map yet is NOT an orphan; a sibling with non-empty `paths` absent
     from the map IS an orphan; `feature_dirs_on_disk` still lists both.
  7. Anomaly classification + no-crash: a dir with NO feature.json and a dir
     with a MALFORMED feature.json (both absent from the map) are still
     surfaced as orphans, and the detector does not crash.

Run non-interactively. Exits non-zero on failure.

Version: 0.2.0
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


def _write_feature_json(feature_dir, paths):
    """Write a minimal feature.json with the given top-level `paths` (the shape
    scaffold-feature.py writes). A greenfield feature has `paths: []`."""
    with open(os.path.join(feature_dir, "feature.json"), "w",
              encoding="utf-8") as f:
        json.dump({"name": os.path.basename(feature_dir),
                   "version": "0.1.0", "paths": paths}, f)


def _make_feature_dirs(rabbit_project_dir, names, paths=None):
    """Create on-disk feature dirs. Each dir gets a feature.json with NON-EMPTY
    `paths` by default (a real feature that belongs in the project-map), so an
    unmapped one is a TRUE orphan. Pass `paths=[]` for greenfield dirs."""
    if paths is None:
        paths = ["src/**"]
    feats_root = os.path.join(rabbit_project_dir, "features")
    for n in names:
        d = os.path.join(feats_root, n)
        os.makedirs(d, exist_ok=True)
        _write_feature_json(d, paths)
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


# --- Check 1: non-greenfield dirs on disk, NO project-map.json -> orphans ----
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

# --- Check 6: greenfield (paths=[]) absent from map is NOT an orphan (#1042) --
# A greenfield feature has paths=[] by design and is INTENTIONALLY never written
# to project-map.json, so flagging it as an orphan is a false positive. Only the
# non-empty-paths sibling, absent from the map, is a true orphan.
with tempfile.TemporaryDirectory() as td6:
    rabbit_root = _make_plugin_tree(td6)
    rp = os.path.join(rabbit_root, "rabbit-project")
    # green-feature: greenfield (paths=[]) — absent from map BY DESIGN.
    _make_feature_dirs(rp, ["green-feature"], paths=[])
    # real-feature: non-empty paths, absent from map -> a TRUE orphan.
    _make_feature_dirs(rp, ["real-feature"], paths=["src/real/**"])
    res = _run_detect(rabbit_root, td6)
    on_disk = set(res.get("feature_dirs_on_disk") or [])
    if on_disk != {"green-feature", "real-feature"}:
        fail("greenfield: feature_dirs_on_disk must list ALL dirs incl. "
             f"greenfield; got {on_disk!r}")
    orphans = set(res.get("orphan_feature_dirs") or [])
    if "green-feature" in orphans:
        fail("greenfield: a paths=[] dir absent from the map is NOT an orphan; "
             f"got {orphans!r}")
    if orphans != {"real-feature"}:
        fail("greenfield: only the non-empty-paths dir absent from the map is "
             f"an orphan; got {orphans!r}")

# --- Check 7: missing / malformed feature.json -> still orphan, no crash ------
# A dir with NO feature.json or a malformed one is genuinely inconsistent: it
# cannot be proven greenfield, so the SAFE classification keeps it an orphan,
# and the detector must NOT crash reading it.
with tempfile.TemporaryDirectory() as td7:
    rabbit_root = _make_plugin_tree(td7)
    rp = os.path.join(rabbit_root, "rabbit-project")
    feats_root = os.path.join(rp, "features")
    # no-json-feature: a bare dir, no feature.json at all.
    os.makedirs(os.path.join(feats_root, "no-json-feature"), exist_ok=True)
    # bad-json-feature: a feature.json that is not valid JSON.
    bad = os.path.join(feats_root, "bad-json-feature")
    os.makedirs(bad, exist_ok=True)
    with open(os.path.join(bad, "feature.json"), "w", encoding="utf-8") as f:
        f.write("{ this is not valid json")
    res = _run_detect(rabbit_root, td7)
    orphans = set(res.get("orphan_feature_dirs") or [])
    if orphans != {"no-json-feature", "bad-json-feature"}:
        fail("anomaly: a missing or malformed feature.json absent from the map "
             f"must still be surfaced as an orphan; got {orphans!r}")

print("All checks passed.")
