#!/usr/bin/env python3
"""test-step4-skill-batch-interface.py — Step 4 layering guard (#921).

End-to-end test that rabbit-decompose's Step 4 plugin-mode scaffold dispatch
goes through the rabbit-feature-scaffold SKILL's declared batch interface
(`skills/rabbit-feature-scaffold/scripts/scaffold-batch.py --batch <file>`),
NOT by shelling out to the rabbit-feature scaffolder implementation detail
(`scripts/scaffold-feature.py --batch <file>`) directly.

The skill is the declared cross-feature interface; the scaffolder script is an
implementation detail of rabbit-feature. Before #921 handoff-scaffold.py
violated that layering by invoking scaffold-feature.py --batch directly. Piece 1
published a skill-level batch surface (scaffold-batch.py, exit codes 0/1/2
mirrored); this piece routes decompose's call site through it.

The test runs the REAL handoff-scaffold.py inside a temp plugin tree whose
rabbit-feature surface is replaced by RECORDING shims for BOTH the skill batch
script and the scaffolder script. Because handoff-scaffold.py anchors its
scaffolder resolution by walking upward from its own __file__ location, the
real script is copied into the temp tree so the walk lands on the shims. The
test then asserts:

  1. The plugin-mode dispatch invokes the skill batch shim
     (scaffold-batch.py --batch <file>) and does NOT invoke the
     scaffold-feature.py shim directly.
  2. The batch JSON file authored by handoff-scaffold.py is preserved and is
     handed to the skill batch interface unchanged (its content equals the
     accepted feature list).
  3. Exit-code propagation works: when the skill batch interface exits 1,
     handoff-scaffold.py exits 1 and reports dispatched=false; when it exits 0,
     handoff-scaffold.py exits 0 and reports dispatched=true.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when Step 4 scaffold hand-off is provided natively by
    the rabbit CLI, retiring the companion handoff-scaffold.py script.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REAL_SCRIPT = os.path.join(FEATURE_DIR, "scripts", "handoff-scaffold.py")
# The real rabbit-meta mode_detection lib, copied into the temp tree so the
# real detect_mode (structural plugin signature) drives the run.
REPO_ROOT = os.path.abspath(os.path.join(FEATURE_DIR, "..", "..", ".."))
REAL_MODE_DETECTION = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-meta", "lib", "mode_detection.py")

FEATURES = [
    {"name": "feature-one", "globs": ["src/one/**/*"]},
    {"name": "feature-two", "globs": ["src/two/**/*"]},
]

# A recording shim: writes its argv (one per line) to RECORD_FILE, then exits
# with the code named by the SHIM_EXIT env var (default 0).
_SHIM = (
    "#!/usr/bin/env python3\n"
    "import os, sys\n"
    "tag = {tag!r}\n"
    "rec = os.environ['RECORD_FILE']\n"
    "with open(rec, 'a', encoding='utf-8') as f:\n"
    "    f.write(tag + '\\t' + '\\t'.join(sys.argv[1:]) + '\\n')\n"
    "sys.exit(int(os.environ.get('SHIM_EXIT', '0')))\n"
)


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _build_plugin_tree(parent):
    """Build a temp plugin tree:

        host-project/                <- non-.rabbit sibling => plugin mode
          README.md
          .rabbit/                   <- rabbit root
            .claude/features/
              rabbit-decompose/scripts/handoff-scaffold.py   (real, copied)
              rabbit-feature/scripts/scaffold-feature.py      (SHIM, tag=SF)
              rabbit-feature/skills/rabbit-feature-scaffold/
                scripts/scaffold-batch.py                     (SHIM, tag=SB)
              rabbit-meta/lib/mode_detection.py               (real, copied)

    Returns (rabbit_root, copied_handoff_script).
    """
    host = os.path.join(parent, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    features = os.path.join(rabbit_root, ".claude", "features")

    # decompose: copy the REAL handoff-scaffold.py
    dec_scripts = os.path.join(features, "rabbit-decompose", "scripts")
    os.makedirs(dec_scripts)
    handoff = os.path.join(dec_scripts, "handoff-scaffold.py")
    shutil.copyfile(REAL_SCRIPT, handoff)

    # rabbit-meta: copy the REAL mode_detection lib (real detect_mode)
    meta_lib = os.path.join(features, "rabbit-meta", "lib")
    os.makedirs(meta_lib)
    shutil.copyfile(
        REAL_MODE_DETECTION, os.path.join(meta_lib, "mode_detection.py"))

    # rabbit-feature scaffolder: SHIM (must NOT be invoked directly)
    feat_scripts = os.path.join(features, "rabbit-feature", "scripts")
    os.makedirs(feat_scripts)
    with open(os.path.join(feat_scripts, "scaffold-feature.py"), "w",
              encoding="utf-8") as f:
        f.write(_SHIM.format(tag="SF"))

    # rabbit-feature-scaffold SKILL batch interface: SHIM (the declared path)
    sb_scripts = os.path.join(
        features, "rabbit-feature", "skills",
        "rabbit-feature-scaffold", "scripts")
    os.makedirs(sb_scripts)
    with open(os.path.join(sb_scripts, "scaffold-batch.py"), "w",
              encoding="utf-8") as f:
        f.write(_SHIM.format(tag="SB"))

    return rabbit_root, handoff


def _write_features_file(d):
    path = os.path.join(d, "accepted.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(FEATURES, f)
    return path


def _run_dispatch(handoff, rabbit_root, features_file, record_file,
                  shim_exit, workdir):
    env = dict(os.environ)
    env["RECORD_FILE"] = record_file
    env["SHIM_EXIT"] = str(shim_exit)
    proc = subprocess.run(
        [sys.executable, handoff,
         "--features", features_file,
         "--rabbit-root", rabbit_root],
        capture_output=True, text=True, cwd=workdir, env=env,
    )
    return proc


def _read_records(record_file):
    if not os.path.isfile(record_file):
        return []
    with open(record_file, encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f if line.strip()]


if not os.path.isfile(REAL_SCRIPT):
    fail(f"missing handoff-scaffold.py: {REAL_SCRIPT}")
if not os.path.isfile(REAL_MODE_DETECTION):
    fail(f"missing rabbit-meta mode_detection lib: {REAL_MODE_DETECTION}")

# --- Check 1 + 2: success path routes through the skill batch interface ------
with tempfile.TemporaryDirectory() as td:
    rabbit_root, handoff = _build_plugin_tree(td)
    feats = _write_features_file(td)
    record_file = os.path.join(td, "record-ok.tsv")

    proc = _run_dispatch(handoff, rabbit_root, feats, record_file, 0, td)
    if proc.returncode != 0:
        fail(f"success dispatch exited {proc.returncode}; stderr:\n{proc.stderr}")

    records = _read_records(record_file)
    tags = [r[0] for r in records]
    if "SF" in tags:
        fail("Step 4 invoked scaffold-feature.py DIRECTLY (tag SF) — the "
             "layering violation #921 fixes; it must go through the skill "
             f"batch interface. records={records!r}")
    if "SB" not in tags:
        fail("Step 4 did NOT invoke the rabbit-feature-scaffold skill batch "
             f"interface (scaffold-batch.py, tag SB). records={records!r}")

    sb_rows = [r for r in records if r[0] == "SB"]
    if len(sb_rows) != 1:
        fail(f"expected exactly one skill batch invocation, got {sb_rows!r}")
    sb_args = sb_rows[0][1:]
    if sb_args[:1] != ["--batch"]:
        fail(f"skill batch interface not called with --batch; args={sb_args!r}")
    if len(sb_args) != 2:
        fail(f"--batch must carry exactly the batch file path; args={sb_args!r}")
    batch_path = sb_args[1]
    if not os.path.isfile(batch_path):
        fail(f"batch file handed to the skill interface is missing: {batch_path}")
    with open(batch_path, encoding="utf-8") as f:
        written = json.load(f)
    if written != FEATURES:
        fail("batch JSON authoring not preserved: file handed to the skill "
             f"interface does not equal the accepted feature list; got {written!r}")

    plan = json.loads(proc.stdout)
    if plan.get("dispatched") is not True:
        fail(f"success dispatch did not report dispatched=true; plan={plan!r}")
    if plan.get("branch") != "batch" or plan.get("mode") != "plugin":
        fail(f"success dispatch wrong mode/branch; plan={plan!r}")

# --- Check 3: exit-code propagation (skill interface exits 1) ----------------
with tempfile.TemporaryDirectory() as td:
    rabbit_root, handoff = _build_plugin_tree(td)
    feats = _write_features_file(td)
    record_file = os.path.join(td, "record-fail.tsv")

    proc = _run_dispatch(handoff, rabbit_root, feats, record_file, 1, td)
    if proc.returncode != 1:
        fail("skill batch interface exited 1 but handoff-scaffold.py exited "
             f"{proc.returncode} (exit-code propagation broken); "
             f"stderr:\n{proc.stderr}")
    records = _read_records(record_file)
    tags = [r[0] for r in records]
    if "SF" in tags:
        fail(f"failure path still invoked scaffold-feature.py directly; "
             f"records={records!r}")
    if "SB" not in tags:
        fail(f"failure path did not invoke the skill batch interface; "
             f"records={records!r}")
    plan = json.loads(proc.stdout)
    if plan.get("dispatched") is not False:
        fail(f"failure dispatch did not report dispatched=false; plan={plan!r}")

print("All checks passed.")
