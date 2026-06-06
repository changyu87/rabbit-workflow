#!/usr/bin/env python3
"""test-detect-existing-project-map.py — existing-project-map detection guard
(#925).

End-to-end test of rabbit-decompose's pre-Step-2 existing-decomposition
detection (spec Invariant 8). Before #925 the skill blindly re-proposed ALL
features even when the project was already decomposed, making output
redundant/confusing. The fix adds a deterministic, script-backed detection
step to `scripts/handoff-scaffold.py`: when a `project-map.json` already exists
with a non-empty `features` map, the skill presents a SUMMARY of the existing
features and offers a three-way branch — (a) skip, (b) add only the
new/unrabbified features, (c) re-decompose (full) — instead of re-proposing
everything.

This test asserts, end-to-end:

  1. `handoff-scaffold.py --detect-existing` against a temp tree whose
     project-map.json carries a non-empty features map reports
     `existing: true`, enumerates the existing feature names (the SUMMARY
     payload), and offers the three-way branch options skip / add-new /
     re-decompose.
  2. With a candidate feature list supplied (`--features`), the detector
     classifies candidates into `already_rabbified` (name present in the
     existing map) vs `new` (absent) — so branch (b) "add" proposes ONLY
     the new/unrabbified features.
  3. With NO project-map.json (or an empty features map), the detector
     reports `existing: false` (first-run behavior unchanged — the skill
     proceeds to its normal propose flow).
  4. The detection is mode-driven (reuses detect_mode): in plugin mode the
     project-map is read at `<rabbit-root>/rabbit-project/project-map.json`;
     in standalone mode at `<rabbit-root>/.rabbit/rabbit-project/project-map.json`.
  5. The SKILL.md body references the detection step (--detect-existing) and
     documents the three-way skip / add / re-decompose branch.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when existing-decomposition detection is provided
    natively by the rabbit CLI, retiring the companion handoff-scaffold.py
    detector.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "handoff-scaffold.py")
SKILL_MD = os.path.join(FEATURE_DIR, "skills", "rabbit-decompose", "SKILL.md")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _run_detect(rabbit_root, workdir, features_file=None):
    argv = [sys.executable, SCRIPT, "--detect-existing",
            "--rabbit-root", rabbit_root]
    if features_file is not None:
        argv += ["--features", features_file]
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=workdir)
    if proc.returncode != 0:
        fail(f"handoff-scaffold.py --detect-existing exited "
             f"{proc.returncode}; stderr:\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"--detect-existing did not emit JSON: {e}; "
             f"stdout:\n{proc.stdout}")


def _write_features_file(d, features):
    path = os.path.join(d, "accepted.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(features, f)
    return path


def _write_project_map(rabbit_project_dir, features):
    os.makedirs(rabbit_project_dir, exist_ok=True)
    pmap = {"schema_version": "1.0.0", "features": features}
    path = os.path.join(rabbit_project_dir, "project-map.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pmap, f)
    return path


def _make_plugin_tree(parent):
    """A `.rabbit/` dir with a non-.rabbit sibling -> detect_mode == plugin.

    The rabbit-root IS the `.rabbit` dir; its project-map lives at
    `<.rabbit>/rabbit-project/project-map.json`."""
    host = os.path.join(parent, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    os.makedirs(rabbit_root)
    return rabbit_root


def _make_standalone_tree(parent):
    """A dir NOT named `.rabbit` -> detect_mode == standalone.

    Its project-map lives at `<root>/.rabbit/rabbit-project/project-map.json`."""
    root = os.path.join(parent, "standalone-root")
    os.makedirs(root)
    return root


if not os.path.isfile(SCRIPT):
    fail(f"missing orchestrator script: {SCRIPT}")
if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")


EXISTING = {
    "alpha-feature": {"paths": ["src/alpha/**"],
                      "feature_dir": "rabbit-project/features/alpha-feature"},
    "beta-feature": {"paths": ["src/beta/**"],
                     "feature_dir": "rabbit-project/features/beta-feature"},
}


# --- Check 1: existing project-map -> existing:true, summary, three branches -
with tempfile.TemporaryDirectory() as td:
    rabbit_root = _make_plugin_tree(td)
    _write_project_map(os.path.join(rabbit_root, "rabbit-project"), EXISTING)
    res = _run_detect(rabbit_root, td)
    if res.get("existing") is not True:
        fail(f"existing project-map: expected existing=True, got "
             f"{res.get('existing')!r}")
    names = set(res.get("existing_features") or [])
    if names != {"alpha-feature", "beta-feature"}:
        fail("existing project-map: SUMMARY must enumerate the existing "
             f"feature names; got {names!r}")
    opts = set(res.get("options") or [])
    if not {"skip", "add", "re-decompose"} <= opts:
        fail("existing project-map: detector must offer the three-way branch "
             f"skip / add / re-decompose; got options {opts!r}")

# --- Check 2: candidate classification -> only new in 'add' ------------------
with tempfile.TemporaryDirectory() as td2:
    rabbit_root = _make_plugin_tree(td2)
    _write_project_map(os.path.join(rabbit_root, "rabbit-project"), EXISTING)
    candidates = [
        {"name": "alpha-feature", "globs": ["src/alpha/**"]},   # already rabbified
        {"name": "gamma-feature", "globs": ["src/gamma/**"]},   # new
        {"name": "delta-feature", "globs": ["src/delta/**"]},   # new
    ]
    feats = _write_features_file(td2, candidates)
    res = _run_detect(rabbit_root, td2, features_file=feats)
    if res.get("existing") is not True:
        fail("candidate classification: expected existing=True")
    already = {f.get("name") for f in (res.get("already_rabbified") or [])}
    new = {f.get("name") for f in (res.get("new") or [])}
    if already != {"alpha-feature"}:
        fail("candidate classification: already_rabbified must be the "
             f"candidates present in the existing map; got {already!r}")
    if new != {"gamma-feature", "delta-feature"}:
        fail("candidate classification: 'add' branch must propose ONLY the "
             f"new/unrabbified candidates; got {new!r}")

# --- Check 3: no project-map (and empty map) -> existing:false (first-run) ---
with tempfile.TemporaryDirectory() as td3:
    rabbit_root = _make_plugin_tree(td3)
    res = _run_detect(rabbit_root, td3)
    if res.get("existing") is not False:
        fail("no project-map: first-run behavior must be unchanged "
             f"(existing=False); got {res.get('existing')!r}")

with tempfile.TemporaryDirectory() as td3b:
    rabbit_root = _make_plugin_tree(td3b)
    _write_project_map(os.path.join(rabbit_root, "rabbit-project"), {})
    res = _run_detect(rabbit_root, td3b)
    if res.get("existing") is not False:
        fail("empty features map: must be treated as first-run "
             f"(existing=False); got {res.get('existing')!r}")

# --- Check 4: mode-driven path resolution (standalone) ----------------------
with tempfile.TemporaryDirectory() as td4:
    root = _make_standalone_tree(td4)
    _write_project_map(
        os.path.join(root, ".rabbit", "rabbit-project"), EXISTING)
    res = _run_detect(root, td4)
    if res.get("mode") != "standalone":
        fail(f"standalone tree: expected mode 'standalone', got "
             f"{res.get('mode')!r}")
    if res.get("existing") is not True:
        fail("standalone tree: project-map under .rabbit/rabbit-project must "
             "be detected (existing=True)")
    names = set(res.get("existing_features") or [])
    if names != {"alpha-feature", "beta-feature"}:
        fail(f"standalone tree: SUMMARY names wrong; got {names!r}")

# --- Check 5: SKILL.md references detection + three-way branch ---------------
with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

if "--detect-existing" not in skill_text:
    fail("SKILL.md does not reference the --detect-existing detection step")

low = skill_text.lower()
for token in ("skip", "add", "re-decompose"):
    if token not in low:
        fail(f"SKILL.md does not document the three-way branch option "
             f"{token!r}")
if "project-map.json" not in skill_text:
    fail("SKILL.md does not mention project-map.json in the detection step")

print("All checks passed.")
