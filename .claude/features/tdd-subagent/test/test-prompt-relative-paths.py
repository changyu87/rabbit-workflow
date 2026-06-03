#!/usr/bin/env python3
"""Inv 58 — assembled-prompt paths are repo-RELATIVE, not main-repo-absolute
(issue #527).

The four filesystem-path slots dispatch-tdd-subagent.py interpolates into the
assembled prompt — feature_dir, tdd_step_py, scope_marker_path,
tdd_report_path — MUST be emitted as paths RELATIVE to the repo root
(os.path.relpath(<abs>, repo_root)), and the repo_root slot itself MUST be
emitted as '.'. The subagent resolves every baked path from its CURRENT
WORKING DIRECTORY, so a worktree-isolated dispatch operates on its own tree.

Two e2e scenarios run dispatch-tdd-subagent.py as a subprocess:

  A) Standalone (live repo, no .rabbit/.runtime/mode == 'plugin'):
     - assembled prompt contains NO occurrence of the absolute repo_root
       prefix,
     - feature_dir appears as `.claude/features/tdd-subagent`,
     - tdd_step_py appears as
       `.claude/features/tdd-subagent/scripts/tdd-step.py`,
     - the LOCK/UNLOCK scope-marker lines use the relative
       `.rabbit-scope-active-tdd-subagent` form,
     - the STEP 7 tdd-report Path is the relative
       `.rabbit/tdd-report-tdd-subagent.json` form,
     - the repo_root references resolve to `.` (e.g. the publish-loop line
       referencing `./.claude/features/contract/lib/publish.py`).

  B) Plugin (tmpdir fixture, .rabbit/.runtime/mode == 'plugin',
     RABBIT_ROOT=<tmp>/.rabbit): the relativization is mode-agnostic — the
     plugin-mode scope marker `<rabbit_root>/.runtime/scope-active-<feature>`
     relativizes to `.runtime/scope-active-<feature>` and the plugin-mode
     report `<rabbit_root>/tdd-report-<feature>.json` relativizes to
     `tdd-report-<feature>.json`; neither carries the absolute rabbit_root
     prefix.
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
    """Strip the embedded SPEC block before grepping for the absolute
    prefix. The SPEC block embeds the feature's spec.md verbatim, whose
    Inv 58 prose legitimately contains absolute-path examples and the
    os.path.join(repo_root, ...) reference being deprecated. We assert on
    the dispatcher's EXECUTABLE instructions, not the embedded spec text.
    """
    return re.sub(
        r"═+\nSPEC\n═+\n.*?(?=═+\nE2E TEST RULE)",
        "[[SPEC BLOCK STRIPPED]]\n",
        prompt,
        count=1,
        flags=re.DOTALL,
    )


def _populate_rabbit_root(root):
    src_features = os.path.join(REPO_ROOT, ".claude", "features")
    dst_features = os.path.join(root, ".claude", "features")
    for feat in ("contract", "tdd-subagent", "policy"):
        src = os.path.join(src_features, feat)
        dst = os.path.join(dst_features, feat)
        if os.path.isdir(src):
            shutil.copytree(src, dst)


def _make_project_feature(rabbit_root, feature_name):
    feat_dir = os.path.join(rabbit_root, "rabbit-project", "features",
                            feature_name)
    os.makedirs(feat_dir)
    _write(os.path.join(feat_dir, "feature.json"),
           '{"name": "' + feature_name + '", "version": "0.1.0", '
           '"owner": "x", "summary": "x", '
           '"surface": {"hooks": [], "commands": [], "skills": []}, '
           '"tdd_state": "spec"}')
    spec = os.path.join(feat_dir, "docs", "spec", "spec.md")
    _write(spec, "# " + feature_name + " spec\n")
    return spec


def _extract_lock_body(prompt):
    m = re.search(r"STEP 1 — LOCK\n═+\n(.*?)\n═+\nSTEP 2", prompt, re.DOTALL)
    return m.group(1) if m else None


def _extract_unlock_body(prompt):
    m = re.search(r"STEP 8 — UNLOCK\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Scenario A: standalone — live repo.
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
    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "tdd-subagent",
         "--spec", SPEC_PATH],
        capture_output=True, text=True, env=env,
    )
    if res.returncode != 0:
        ko(f"scenario A: dispatch failed rc={res.returncode}: {res.stderr!r}")
    else:
        prompt = res.stdout
        body = _strip_spec_block(prompt)

        # (a) NO occurrence of the absolute repo_root prefix in the
        # executable instructions.
        abs_prefix = REPO_ROOT.rstrip("/") + "/"
        if abs_prefix not in body:
            ok("scenario A: assembled prompt contains NO absolute repo_root "
               "prefix")
        else:
            idx = body.find(abs_prefix)
            ctx = body[max(0, idx - 30): idx + 90]
            ko(f"scenario A: absolute repo_root prefix leaked; context: "
               f"{ctx!r}")

        # (b) feature_dir appears in repo-relative form (a `.claude/...`
        # path with no path segment immediately preceding it, i.e. not an
        # absolute prefix). The lookbehind rejects `<abs>/.claude/...`.
        if re.search(r"(?<![\w/])\.claude/features/tdd-subagent/test/",
                     body):
            ok("scenario A: feature_dir appears relative "
               "(.claude/features/tdd-subagent)")
        else:
            ko("scenario A: feature_dir not in expected relative form")

        # (c) tdd_step_py appears in repo-relative form.
        if re.search(
                r"(?<![\w/])\.claude/features/tdd-subagent/scripts/"
                r"tdd-step\.py",
                body):
            ok("scenario A: tdd_step_py appears relative "
               "(.claude/features/tdd-subagent/scripts/tdd-step.py)")
        else:
            ko("scenario A: tdd_step_py not in expected relative form")

        # (d) repo_root slot emitted as '.': the publish-loop line resolves
        # to ./.claude/features/contract/lib/publish.py.
        if "./.claude/features/contract/lib/publish.py" in body:
            ok("scenario A: repo_root slot is '.' "
               "(./.claude/features/contract/lib/publish.py)")
        else:
            ko("scenario A: repo_root slot not '.' (publish.py path not "
               "relativized)")

        # (e) LOCK/UNLOCK scope-marker lines use the relative marker path.
        lock_body = _extract_lock_body(prompt)
        unlock_body = _extract_unlock_body(prompt)
        if lock_body and re.search(
                r"touch\s+\.rabbit-scope-active-tdd-subagent\b", lock_body):
            ok("scenario A: LOCK uses relative scope marker "
               "(touch .rabbit-scope-active-tdd-subagent)")
        else:
            ko("scenario A: LOCK scope-marker line not relative")
        if unlock_body and re.search(
                r"rm -f\s+\.rabbit-scope-active-tdd-subagent\b", unlock_body):
            ok("scenario A: UNLOCK uses relative scope marker "
               "(rm -f .rabbit-scope-active-tdd-subagent)")
        else:
            ko("scenario A: UNLOCK scope-marker line not relative")

        # (f) STEP 7 tdd-report Path is the relative form.
        m = re.search(
            r"^\s*Path:\s*(\S+tdd-report-tdd-subagent\.json)\s*$",
            prompt, re.MULTILINE)
        if m is None:
            ko("scenario A: no STEP 7 'Path:' line for tdd-report found")
        elif m.group(1) == ".rabbit/tdd-report-tdd-subagent.json":
            ok("scenario A: STEP 7 tdd-report Path is relative "
               "(.rabbit/tdd-report-tdd-subagent.json)")
        else:
            ko(f"scenario A: STEP 7 tdd-report Path not relative — got "
               f"{m.group(1)!r}")


# ---------------------------------------------------------------------------
# Scenario B: plugin — mode-agnostic relativization.
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
        prompt = res.stdout
        body = _strip_spec_block(prompt)

        # NO occurrence of the absolute rabbit_root prefix.
        abs_prefix = rabbit_root.rstrip("/") + "/"
        if abs_prefix not in body:
            ok("scenario B: assembled prompt contains NO absolute "
               "rabbit_root prefix")
        else:
            idx = body.find(abs_prefix)
            ctx = body[max(0, idx - 30): idx + 90]
            ko(f"scenario B: absolute rabbit_root prefix leaked; context: "
               f"{ctx!r}")

        # Plugin-mode scope marker relativizes to .runtime/scope-active-...
        lock_body = _extract_lock_body(prompt)
        if lock_body and re.search(
                r"touch\s+\.runtime/scope-active-run-ingest\b", lock_body):
            ok("scenario B: LOCK uses relative plugin scope marker "
               "(touch .runtime/scope-active-run-ingest)")
        else:
            ko("scenario B: LOCK plugin scope-marker line not relative")

        # Plugin-mode report relativizes to tdd-report-<feature>.json.
        m = re.search(
            r"^\s*Path:\s*(\S+)\s*$",
            prompt, re.MULTILINE)
        if m is None:
            ko("scenario B: no STEP 7 'Path:' line for tdd-report found")
        elif m.group(1) == "tdd-report-run-ingest.json":
            ok("scenario B: STEP 7 tdd-report Path is relative "
               "(tdd-report-run-ingest.json)")
        else:
            ko(f"scenario B: STEP 7 tdd-report Path not relative — got "
               f"{m.group(1)!r}")


report(passed, failed)
