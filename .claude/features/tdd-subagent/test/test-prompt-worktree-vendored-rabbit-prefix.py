#!/usr/bin/env python3
"""Inv 65 (issue #1146) — in VENDORED mode the `--worktree` re-rooting must
preserve the `.rabbit/` segment.

Vendored Strategy-D dispatch passes BOTH:
  - RABBIT_ROOT=<host>/.rabbit  (so dispatch repo_root is the `.rabbit/`
    install dir, per Inv 47), and
  - --worktree <host>           (the per-session worktree root IS the host
    repo root, where `.rabbit/` is a SUBDIRECTORY).

The five path slots (feature_dir, tdd_step_py, repo_root, scope_marker_path,
tdd_report_path) are computed repo-relative to repo_root (=`.rabbit/`) and then
re-rooted onto the absolute worktree. The bug (#1146): re-rooting joins the
`.rabbit/`-relative form onto the worktree ROOT, dropping the `.rabbit/`
segment, so the emitted absolute paths point at `<host>/.claude/...` instead of
the real `<host>/.rabbit/.claude/...`. A literal consumer cannot find the spec
/ scope marker / tdd-step.py there.

The fix re-roots vendored slots at `<worktree>/.rabbit/` so the subagent's
worktree anchor and the embedded paths share one base. This test runs the live
dispatcher as a subprocess in the vendored fixture and asserts every emitted
absolute path slot carries the `.rabbit/` segment under the worktree.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from _helpers import DISPATCH_PY, REPO_ROOT, report

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
    return re.sub(
        r"═+\nSPEC\n═+\n.*?(?=═+\nE2E TEST RULE)",
        "[[SPEC BLOCK STRIPPED]]\n",
        prompt,
        count=1,
        flags=re.DOTALL,
    )


def _extract_lock_body(prompt):
    m = re.search(r"STEP 1 — LOCK\n═+\n(.*?)\n═+\nSTEP 2", prompt, re.DOTALL)
    return m.group(1) if m else None


def _extract_unlock_body(prompt):
    m = re.search(r"STEP 8 — UNLOCK\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
    return m.group(1) if m else None


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
    feat_dir = os.path.join(
        rabbit_root, "rabbit-project", "features", feature_name)
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
# Vendored fixture: RABBIT_ROOT=<host>/.rabbit AND --worktree <host>.
# Mirrors the live vendored Strategy-D dispatch (#1146): the dispatcher's
# repo_root is the `.rabbit/` install dir, but the per-session worktree root
# is the HOST repo root (one level up).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    host_root = os.path.realpath(tmp)
    rabbit_root = os.path.join(host_root, ".rabbit")
    os.makedirs(rabbit_root)
    _populate_rabbit_root(rabbit_root)
    _write(os.path.join(rabbit_root, ".runtime", "mode"), "vendored")
    proj_spec = _make_project_feature(rabbit_root, "run-ingest")

    env = os.environ.copy()
    env["RABBIT_ROOT"] = rabbit_root

    res = subprocess.run(
        [sys.executable, DISPATCH_PY, "--scope", "run-ingest",
         "--spec", proj_spec, "--worktree", host_root],
        capture_output=True, text=True, env=env,
    )

    if res.returncode != 0:
        ko(f"vendored --worktree dispatch failed rc={res.returncode}: "
           f"{res.stderr!r}")
    else:
        prompt = res.stdout
        body = _strip_spec_block(prompt)

        # The real per-mode anchor under the worktree carries the `.rabbit/`
        # segment. The bug drops it.
        rabbit_prefix = host_root.rstrip("/") + "/.rabbit/"
        bad_prefix = host_root.rstrip("/") + "/.claude/"

        # repo_root slot — appears in the publish-loop publish.py path.
        if f"{rabbit_prefix}.claude/features/contract/lib/publish.py" in body:
            ok("repo_root slot is anchored at <worktree>/.rabbit/ "
               "(publish.py carries .rabbit/ segment)")
        else:
            ko("repo_root slot dropped the .rabbit/ segment — publish.py not "
               f"under {rabbit_prefix}")

        # feature_dir slot — project feature lives under
        # rabbit-project/features/ in vendored mode.
        if (f"{rabbit_prefix}rabbit-project/features/run-ingest/test/"
                in body):
            ok("feature_dir slot is anchored at <worktree>/.rabbit/")
        else:
            ko("feature_dir slot dropped the .rabbit/ segment")

        # tdd_step_py slot.
        if (f"{rabbit_prefix}.claude/features/tdd-subagent/scripts/"
                "tdd-step.py" in body):
            ok("tdd_step_py slot is anchored at <worktree>/.rabbit/")
        else:
            ko("tdd_step_py slot dropped the .rabbit/ segment")

        # Scope marker (vendored shape: <rabbit_root>/.runtime/scope-active-X)
        # re-rooted onto the worktree must be
        # <worktree>/.rabbit/.runtime/scope-active-run-ingest.
        lock_body = _extract_lock_body(prompt)
        unlock_body = _extract_unlock_body(prompt)
        marker = f"{rabbit_prefix}.runtime/scope-active-run-ingest"
        if lock_body and re.search(
                r"touch\s+" + re.escape(marker) + r"\b", lock_body):
            ok("LOCK scope marker is anchored at <worktree>/.rabbit/")
        else:
            ko("LOCK scope marker dropped the .rabbit/ segment")
        if unlock_body and re.search(
                r"rm -f\s+" + re.escape(marker) + r"\b", unlock_body):
            ok("UNLOCK scope marker is anchored at <worktree>/.rabbit/")
        else:
            ko("UNLOCK scope marker dropped the .rabbit/ segment")

        # STEP 7 tdd-report Path. Vendored report rooted at rabbit-root →
        # re-rooted to <worktree>/.rabbit/tdd-report-run-ingest.json.
        m = re.search(
            r"^\s*Path:\s*(\S+tdd-report-run-ingest\.json)\s*$",
            prompt, re.MULTILINE)
        if m is None:
            ko("no STEP 7 'Path:' line for tdd-report found")
        elif m.group(1) == f"{rabbit_prefix}tdd-report-run-ingest.json":
            ok("STEP 7 tdd-report Path is anchored at <worktree>/.rabbit/")
        else:
            ko("STEP 7 tdd-report Path dropped the .rabbit/ segment — got "
               f"{m.group(1)!r}")

        # Regression guard: NO slot may point at <worktree>/.claude/ (the
        # .rabbit/-stripped form the bug produced).
        if bad_prefix not in body:
            ok("no path slot points at the .rabbit/-stripped "
               f"{bad_prefix} form")
        else:
            idx = body.find(bad_prefix)
            ctx = body[max(0, idx - 40): idx + 80]
            ko(f"a path slot leaked the .rabbit/-stripped form; context: "
               f"{ctx!r}")


report(passed, failed)
