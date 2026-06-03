#!/usr/bin/env python3
"""Inv 48 — No doubled `.rabbit/.rabbit/` substring in assembled prompt.

Two scenarios:

  A) Standalone tmpdir (no RABBIT_ROOT env, no .rabbit/.runtime/mode).
     Invoke dispatch.py via subprocess; assert the assembled stdout does
     NOT contain the substring `.rabbit/.rabbit/`.

  B) Plugin tmpdir (.rabbit/.runtime/mode='plugin' + RABBIT_ROOT=<tmp>/.rabbit).
     Invoke dispatch.py; assert the assembled stdout does NOT contain
     `.rabbit/.rabbit/` AND the STEP 7 `Path:` line for the tdd-report
     ends with `/tdd-report-<feature>.json` rooted at the rabbit-root
     (single `.rabbit/`, not doubled).

Both scenarios pin the absence of the doubled substring as the regression
assertion.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from _helpers import DISPATCH_PY, REPO_ROOT, SPEC_PATH, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _strip_spec_block(prompt):
    """Strip the SPEC block from the prompt. The SPEC block embeds the
    feature's spec.md verbatim, which legitimately contains the
    `.rabbit/.rabbit/` substring as documentation of the bug being fixed
    (Inv 48 prose). We're checking that the dispatcher's EXECUTABLE
    instructions (steps 1-8, HANDOFF) don't contain the doubled path —
    so strip the SPEC content before grepping.
    """
    # SPEC block runs from the `SPEC` banner line through the next
    # `═` banner introducing the next section (E2E TEST RULE).
    return re.sub(
        r"═+\nSPEC\n═+\n.*?(?=═+\nE2E TEST RULE)",
        "[[SPEC BLOCK STRIPPED]]\n",
        prompt,
        count=1,
        flags=re.DOTALL,
    )


def _populate_rabbit_root(root):
    """Copy contract/tdd-subagent/policy features into `root`."""
    src_features = os.path.join(REPO_ROOT, ".claude", "features")
    dst_features = os.path.join(root, ".claude", "features")
    for feat in ("contract", "tdd-subagent", "policy"):
        src = os.path.join(src_features, feat)
        dst = os.path.join(dst_features, feat)
        if os.path.isdir(src):
            shutil.copytree(src, dst)


def _make_project_feature(rabbit_root, feature_name):
    feat_dir = os.path.join(rabbit_root, "rabbit-project", "features", feature_name)
    os.makedirs(feat_dir)
    _write(os.path.join(feat_dir, "feature.json"),
           '{"name": "' + feature_name + '", "version": "0.1.0", '
           '"owner": "x", "summary": "x", '
           '"surface": {"hooks": [], "commands": [], "skills": []}, '
           '"tdd_state": "spec"}')
    spec = os.path.join(feat_dir, "docs", "spec", "spec.md")
    _write(spec, "# " + feature_name + " spec\n")
    return spec


# ---------------------------------------------------------------------------
# Scenario A: standalone — no RABBIT_ROOT, no .rabbit/.runtime/mode in tmp.
#
# We use the live repo's own tdd-subagent feature (the live repo is the
# standalone-mode reference). Assert: doubled `.rabbit/.rabbit/` substring
# is absent from the full assembled prompt.
# ---------------------------------------------------------------------------
env = os.environ.copy()
env.pop("RABBIT_ROOT", None)

live_mode = os.path.join(REPO_ROOT, ".rabbit", ".runtime", "mode")
live_mode_value = ""
if os.path.isfile(live_mode):
    with open(live_mode) as _f:
        live_mode_value = _f.read().strip()
if live_mode_value == "plugin":
    ko(f"scenario A precondition: live repo {live_mode} is 'plugin'; "
       "cannot test standalone path here")
else:
    spec_path = SPEC_PATH
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "tdd-subagent",
         "--spec", spec_path],
        capture_output=True, text=True, env=env,
    )
    if res.returncode != 0:
        ko(f"scenario A: dispatch failed rc={res.returncode}: {res.stderr!r}")
    else:
        prompt = _strip_spec_block(res.stdout)
        if ".rabbit/.rabbit/" not in prompt:
            ok("scenario A: assembled prompt contains NO '.rabbit/.rabbit/' "
               "doubled substring")
        else:
            # Locate first occurrence for diagnostic.
            idx = prompt.find(".rabbit/.rabbit/")
            ctx = prompt[max(0, idx - 40): idx + 80]
            ko(f"scenario A: '.rabbit/.rabbit/' leaked into assembled prompt; "
               f"context: {ctx!r}")


# ---------------------------------------------------------------------------
# Scenario B: plugin — `.rabbit/.runtime/mode == 'plugin'` + RABBIT_ROOT set.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    rabbit_root = os.path.join(tmp, ".rabbit")
    os.makedirs(rabbit_root)
    _populate_rabbit_root(rabbit_root)
    _write(os.path.join(rabbit_root, ".runtime", "mode"), "plugin")
    proj_spec = _make_project_feature(rabbit_root, "run-ingest")

    env = os.environ.copy()
    env["RABBIT_ROOT"] = rabbit_root
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "run-ingest",
         "--spec", proj_spec],
        capture_output=True, text=True, env=env,
    )
    if res.returncode != 0:
        ko(f"scenario B: dispatch failed rc={res.returncode}: {res.stderr!r}")
    else:
        prompt = _strip_spec_block(res.stdout)
        if ".rabbit/.rabbit/" not in prompt:
            ok("scenario B: assembled prompt contains NO '.rabbit/.rabbit/' "
               "doubled substring")
        else:
            idx = prompt.find(".rabbit/.rabbit/")
            ctx = prompt[max(0, idx - 40): idx + 80]
            ko(f"scenario B: '.rabbit/.rabbit/' leaked into assembled prompt; "
               f"context: {ctx!r}")

        # Assert the STEP 7 `Path:` line for tdd-report. Inv 58: the
        # tdd_report_path slot is repo-RELATIVE. In plugin mode repo_root IS
        # the rabbit-root, so the plugin report
        # `<rabbit_root>/tdd-report-<feature>.json` relativizes to the bare
        # `tdd-report-<feature>.json` (single segment, no doubled .rabbit/,
        # no absolute prefix).
        expected_path = "tdd-report-run-ingest.json"
        # The Path: line appears in STEP 7 TEST-GREEN body.
        m = re.search(r"^\s*Path:\s*(\S+tdd-report-run-ingest\.json)\s*$",
                      prompt, re.MULTILINE)
        if m is None:
            ko("scenario B: no STEP 7 'Path:' line for tdd-report found")
        elif m.group(1) == expected_path:
            ok(f"scenario B: STEP 7 Path is {expected_path!r} "
               "(relative, no doubled .rabbit/)")
        else:
            ko(f"scenario B: STEP 7 Path mismatch — got {m.group(1)!r}, "
               f"expected {expected_path!r}")


report(passed, failed)
