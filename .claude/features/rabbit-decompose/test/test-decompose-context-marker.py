#!/usr/bin/env python3
"""test-decompose-context-marker.py — Step 4 decompose-context pass-through.

End-to-end test of rabbit-decompose's adoption of the decompose-context
scope-guard pass-through (spec Invariant 9; #923). The batch scaffold flow
must, instead of the undiscoverable manual `.rabbit/.rabbit-scope-override =
'session'` workaround, set a bounded, auto-cleared decompose-context marker
around the batch work:

  1. BEFORE the batch scaffold step, WRITE
     `<repo_root>/.rabbit/.runtime/decompose-active` with `operation` (a
     decompose label), `features` (the exact set of feature NAMES being
     scaffolded this batch), and optionally a bounded `expires`.
  2. Run the batch scaffold / spec-seed work.
  3. AFTER completion (success OR failure), DELETE the marker.

This is SCRIPT-tier: `scripts/handoff-scaffold.py` owns the set/clear via the
`--decompose-context set|clear` subcommand, and the script's own batch
dispatch wraps the work so the marker is cleared even when the scaffolder
fails (try/finally).

Asserts, end-to-end:

  1. `--decompose-context set --features <f>` writes the marker at the
     mode-correct path (plugin → `<rabbit_root>/.runtime/decompose-active`;
     standalone → `<rabbit_root>/.rabbit/.runtime/decompose-active`) with JSON
     `{operation, features:[names...]}` matching piece-1's schema, where
     `features` is exactly the accepted feature NAMES.
  2. `--decompose-context clear` deletes the marker (idempotent — clearing an
     absent marker exits 0).
  3. The script's own batch dispatch (plugin `--features`, not `--plan-only`)
     SETS the marker before invoking the scaffolder and CLEARS it after — even
     when the scaffolder FAILS (non-zero exit). The marker never lingers.
  4. The marker JSON schema matches piece-1's contract: a dict with a
     non-empty string `operation` and a non-empty list of string `features`;
     an optional ISO-8601 `expires` when present parses.
  5. The `SKILL.md` Step 4 body documents the pass-through (`decompose-active`
     set before / clear after) and carries NO reference to the manual
     `.rabbit-scope-override` session workaround as the recommended path.

The vendored-mode marker-path branch is now a dual-accept
`mode in ("vendored", "plugin")` (spec Invariant 10, #988). This test drives
the live `detect_mode`, which currently returns `"plugin"`, so it exercises the
`"plugin"` arm; the `"vendored"` arm is exercised by
`test-dual-accept-vendored-mode.py`.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when the decompose-context scope-guard pass-through is
    superseded by a native rabbit CLI scope mechanism.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "handoff-scaffold.py")
SKILL_MD = os.path.join(FEATURE_DIR, "skills", "rabbit-decompose", "SKILL.md")
REPO_ROOT = os.path.abspath(os.path.join(FEATURE_DIR, "..", "..", ".."))
REAL_MODE_DETECTION = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-meta", "lib",
    "mode_detection.py")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _write_features_file(d, features):
    path = os.path.join(d, "accepted.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(features, f)
    return path


def _make_plugin_tree(parent):
    """A `.rabbit/` dir with a non-.rabbit sibling -> detect_mode == plugin."""
    host = os.path.join(parent, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    os.makedirs(rabbit_root)
    return rabbit_root


def _make_standalone_tree(parent):
    """A dir NOT named `.rabbit` -> detect_mode == standalone."""
    root = os.path.join(parent, "standalone-root")
    os.makedirs(root)
    return root


def _plugin_marker_path(rabbit_root):
    return os.path.join(rabbit_root, ".runtime", "decompose-active")


def _standalone_marker_path(rabbit_root):
    return os.path.join(rabbit_root, ".rabbit", ".runtime", "decompose-active")


def _run(args, workdir):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, cwd=workdir,
    )


def _assert_schema(marker_path, expected_names):
    """The marker JSON must match piece-1's contract."""
    with open(marker_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        fail(f"marker JSON is not an object: {data!r}")
    op = data.get("operation")
    if not isinstance(op, str) or not op:
        fail(f"marker 'operation' must be a non-empty string; got {op!r}")
    feats = data.get("features")
    if not isinstance(feats, list) or not feats:
        fail(f"marker 'features' must be a non-empty list; got {feats!r}")
    for fname in feats:
        if not isinstance(fname, str) or not fname:
            fail(f"marker 'features' entries must be non-empty strings; "
                 f"got {fname!r}")
    if set(feats) != set(expected_names):
        fail(f"marker 'features' must be exactly the accepted feature NAMES "
             f"{sorted(expected_names)}; got {sorted(feats)}")
    exp = data.get("expires")
    if exp is not None:
        raw = str(exp)
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            datetime.datetime.fromisoformat(raw)
        except ValueError:
            fail(f"marker 'expires' is present but not ISO-8601: {exp!r}")


if not os.path.isfile(SCRIPT):
    fail(f"missing handoff-scaffold.py: {SCRIPT}")
if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")

FEATURES = [
    {"name": "feature-one", "globs": ["src/one/**/*"]},
    {"name": "feature-two", "globs": ["src/two/**/*"]},
]
NAMES = {"feature-one", "feature-two"}

# --- Check 1 + 4: set writes the mode-correct marker with the right schema ---
with tempfile.TemporaryDirectory() as td:
    feats = _write_features_file(td, FEATURES)

    # PLUGIN
    plugin_root = _make_plugin_tree(td)
    proc = _run(["--decompose-context", "set",
                 "--features", feats, "--rabbit-root", plugin_root], td)
    if proc.returncode != 0:
        fail(f"plugin set exited {proc.returncode}; stderr:\n{proc.stderr}")
    pm = _plugin_marker_path(plugin_root)
    if not os.path.isfile(pm):
        fail(f"plugin set did not write marker at {pm}")
    _assert_schema(pm, NAMES)

    # STANDALONE
    standalone_root = _make_standalone_tree(td)
    proc = _run(["--decompose-context", "set",
                 "--features", feats, "--rabbit-root", standalone_root], td)
    if proc.returncode != 0:
        fail(f"standalone set exited {proc.returncode}; stderr:\n{proc.stderr}")
    sm = _standalone_marker_path(standalone_root)
    if not os.path.isfile(sm):
        fail(f"standalone set did not write marker at {sm}")
    _assert_schema(sm, NAMES)

    # --- Check 2: clear deletes the marker; idempotent on absent ---
    proc = _run(["--decompose-context", "clear",
                 "--rabbit-root", plugin_root], td)
    if proc.returncode != 0:
        fail(f"plugin clear exited {proc.returncode}; stderr:\n{proc.stderr}")
    if os.path.exists(pm):
        fail(f"plugin clear did not delete marker {pm}")
    # idempotent: clearing again is fine.
    proc = _run(["--decompose-context", "clear",
                 "--rabbit-root", plugin_root], td)
    if proc.returncode != 0:
        fail(f"plugin clear (idempotent) exited {proc.returncode}; "
             f"stderr:\n{proc.stderr}")

    proc = _run(["--decompose-context", "clear",
                 "--rabbit-root", standalone_root], td)
    if proc.returncode != 0:
        fail(f"standalone clear exited {proc.returncode}; "
             f"stderr:\n{proc.stderr}")
    if os.path.exists(sm):
        fail(f"standalone clear did not delete marker {sm}")

# --- Check 3: batch dispatch sets-before / clears-after even on FAILURE -----
# Build a temp plugin tree carrying the REAL handoff-scaffold.py + the REAL
# rabbit-meta detect_mode, plus a FAILING rabbit-feature scaffold-batch.py
# shim. Because handoff-scaffold.py anchors its scaffolder + detect_mode
# resolution by walking upward from its OWN __file__, the real script is
# copied into the temp tree so the walk lands on the shim (same approach as
# test-step4-skill-batch-interface.py). The shim records WHETHER the
# decompose-active marker exists at dispatch time (proving set-before), then
# exits 1 (failure). Afterward the marker must be gone (clear-on-failure).
if not os.path.isfile(REAL_MODE_DETECTION):
    fail(f"missing rabbit-meta mode_detection lib: {REAL_MODE_DETECTION}")

with tempfile.TemporaryDirectory() as td:
    host = os.path.join(td, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    feat_root = os.path.join(rabbit_root, ".claude", "features")

    # decompose: copy the REAL handoff-scaffold.py so the walk-up lands here.
    dec_scripts = os.path.join(feat_root, "rabbit-decompose", "scripts")
    os.makedirs(dec_scripts)
    handoff = os.path.join(dec_scripts, "handoff-scaffold.py")
    shutil.copyfile(SCRIPT, handoff)

    # rabbit-meta: copy the REAL detect_mode (structural plugin signature).
    meta_lib = os.path.join(feat_root, "rabbit-meta", "lib")
    os.makedirs(meta_lib)
    shutil.copyfile(
        REAL_MODE_DETECTION, os.path.join(meta_lib, "mode_detection.py"))

    # rabbit-feature scaffold-batch.py shim: record marker presence, exit 1.
    sb_dir = os.path.join(feat_root, "rabbit-feature", "skills",
                          "rabbit-feature-scaffold", "scripts")
    os.makedirs(sb_dir)
    marker_record = os.path.join(td, "scaffold-saw-marker.txt")
    expected_marker = _plugin_marker_path(rabbit_root)
    with open(os.path.join(sb_dir, "scaffold-batch.py"), "w") as f:
        f.write(
            "import os, sys\n"
            f"open({marker_record!r}, 'w').write(\n"
            f"    'present' if os.path.isfile({expected_marker!r}) "
            "else 'absent')\n"
            "sys.exit(1)\n"
        )

    feats = _write_features_file(td, FEATURES)
    # Run the real batch dispatch (NOT --plan-only): set marker, dispatch the
    # failing shim, clear marker in finally.
    proc = subprocess.run(
        [sys.executable, handoff,
         "--features", feats, "--rabbit-root", rabbit_root],
        capture_output=True, text=True, cwd=host,
    )
    # The dispatch fails (shim exits 1), so the script returns non-zero.
    if proc.returncode == 0:
        fail("batch dispatch with a FAILING scaffolder shim unexpectedly "
             f"exited 0; stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    # The scaffolder must have observed the marker present at dispatch time.
    if not os.path.isfile(marker_record):
        fail("scaffolder shim was never invoked (no record file) — the batch "
             f"dispatch did not run it; stderr:\n{proc.stderr}")
    with open(marker_record) as f:
        saw = f.read().strip()
    if saw != "present":
        fail("decompose-active marker was NOT set before the batch dispatch "
             f"(scaffolder saw it {saw!r})")
    # And the marker must be CLEARED afterward despite the failure.
    if os.path.exists(expected_marker):
        fail("decompose-active marker LINGERED after a FAILED batch dispatch — "
             "it must be cleared even on failure (try/finally)")

# --- Check 6: an EXTERNALLY-set marker is PRESERVED by the batch dispatch ----
# The realistic SKILL flow sets the marker in Step 4-A (it must span the later
# spec-seed step), then runs the batch dispatch, then clears in Step 4-D. The
# script's own batch self-guard is OWN-ONLY: when a marker is already present
# it must leave it untouched so the spec-seed step still sees it. Use a
# SUCCEEDING scaffolder shim here so the dispatch returns 0.
with tempfile.TemporaryDirectory() as td:
    host = os.path.join(td, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    feat_root = os.path.join(rabbit_root, ".claude", "features")

    dec_scripts = os.path.join(feat_root, "rabbit-decompose", "scripts")
    os.makedirs(dec_scripts)
    handoff = os.path.join(dec_scripts, "handoff-scaffold.py")
    shutil.copyfile(SCRIPT, handoff)

    meta_lib = os.path.join(feat_root, "rabbit-meta", "lib")
    os.makedirs(meta_lib)
    shutil.copyfile(
        REAL_MODE_DETECTION, os.path.join(meta_lib, "mode_detection.py"))

    sb_dir = os.path.join(feat_root, "rabbit-feature", "skills",
                          "rabbit-feature-scaffold", "scripts")
    os.makedirs(sb_dir)
    marker_record = os.path.join(td, "scaffold-saw-marker2.txt")
    expected_marker = _plugin_marker_path(rabbit_root)
    with open(os.path.join(sb_dir, "scaffold-batch.py"), "w") as f:
        f.write(
            "import os, sys\n"
            f"open({marker_record!r}, 'w').write(\n"
            f"    'present' if os.path.isfile({expected_marker!r}) "
            "else 'absent')\n"
            "sys.exit(0)\n"
        )

    feats = _write_features_file(td, FEATURES)
    # Step 4-A: SET the marker externally (the SKILL's outer orchestration).
    proc = subprocess.run(
        [sys.executable, handoff, "--decompose-context", "set",
         "--features", feats, "--rabbit-root", rabbit_root],
        capture_output=True, text=True, cwd=host,
    )
    if proc.returncode != 0:
        fail(f"external set exited {proc.returncode}; stderr:\n{proc.stderr}")
    if not os.path.isfile(expected_marker):
        fail("external set did not write the marker")
    # Step 4-B: batch dispatch (succeeds). The pre-existing marker must remain.
    proc = subprocess.run(
        [sys.executable, handoff,
         "--features", feats, "--rabbit-root", rabbit_root],
        capture_output=True, text=True, cwd=host,
    )
    if proc.returncode != 0:
        fail(f"batch dispatch (own-only) exited {proc.returncode}; "
             f"stderr:\n{proc.stderr}")
    with open(marker_record) as f:
        if f.read().strip() != "present":
            fail("scaffolder did not see the externally-set marker")
    if not os.path.isfile(expected_marker):
        fail("batch dispatch CLEARED an externally-set marker — the own-only "
             "self-guard must leave the outer orchestration's marker for the "
             "spec-seed step")
    # Step 4-D: the outer orchestration clears it.
    proc = subprocess.run(
        [sys.executable, handoff, "--decompose-context", "clear",
         "--rabbit-root", rabbit_root],
        capture_output=True, text=True, cwd=host,
    )
    if proc.returncode != 0:
        fail(f"outer clear exited {proc.returncode}; stderr:\n{proc.stderr}")
    if os.path.exists(expected_marker):
        fail("outer clear did not delete the marker")

# --- Check 5: SKILL.md documents the pass-through, not the manual override ---
with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

if "decompose-active" not in skill_text:
    fail("SKILL.md Step 4 does not document the decompose-active pass-through")
if "--decompose-context" not in skill_text:
    fail("SKILL.md Step 4 does not invoke the --decompose-context set/clear "
         "script subcommand")
# The manual session-override workaround must not be recommended.
if ".rabbit-scope-override" in skill_text:
    fail("SKILL.md still references the manual .rabbit-scope-override session "
         "workaround; the pass-through replaces it")

print("All checks passed.")
