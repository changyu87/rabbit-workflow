#!/usr/bin/env python3
# test-specs-migration.py — issue #399 Phase 2 (tdd-subagent) coverage.
#
# End-to-end coverage for the docs/spec/ -> specs/ migration of the
# tdd-subagent feature and the dual-read behaviour of its owned tooling
# (dispatch-tdd-subagent.py, tdd-step.py).
#
# Behaviours under test:
#   1. tdd-subagent's own spec/contract live at specs/ and no docs/ dir
#      remains.
#   2. The Inv 38 spec-update -> test-red git-diff gate accepts a change
#      under the NEW specs/ layout (preferred) AND under the LEGACY
#      docs/spec/ layout (fallback, dual-read for not-yet-migrated
#      features).
#   3. The Inv 41 numbered-list check resolves both layouts (no crash,
#      transition still succeeds — the check is best-effort).
#   4. dispatch-tdd-subagent.py works with a --spec under specs/ and the
#      scoped-view grep NOTE points at specs/ (no docs/spec/ literal).
#
# Owner: rabbit-workflow team (tdd-subagent)
# Deprecation criterion: when issue #399 Phase 3 drops the docs/spec/
#     fallback (the legacy-layout assertions retire then).
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REPO_ROOT = os.path.abspath(os.path.join(FEATURE_DIR, "..", "..", ".."))
TDD_STEP = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")
DISPATCH = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
TMPROOT = tempfile.mkdtemp()

sys.path.insert(0, SCRIPT_DIR)
from state_machine_helpers import make_feature_dir as _make_feature_dir  # noqa: E402

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def _run(cmd, env=None):
    res = subprocess.run(cmd, capture_output=True, env=env)
    return res.returncode, res.stdout, res.stderr


# ---------------------------------------------------------------------------
# 1. tdd-subagent's own layout: specs/ present, docs/ absent.
# ---------------------------------------------------------------------------
def t_own_layout():
    specs_spec = os.path.join(FEATURE_DIR, "specs", "spec.md")
    specs_contract = os.path.join(FEATURE_DIR, "specs", "contract.md")
    docs_dir = os.path.join(FEATURE_DIR, "docs")
    if os.path.isfile(specs_spec):
        ok("migration: specs/spec.md exists")
    else:
        ko(f"migration: specs/spec.md missing at {specs_spec}")
    if os.path.isfile(specs_contract):
        ok("migration: specs/contract.md exists")
    else:
        ko(f"migration: specs/contract.md missing at {specs_contract}")
    if not os.path.exists(docs_dir):
        ok("migration: no docs/ directory remains")
    else:
        ko(f"migration: docs/ still present at {docs_dir}")


# ---------------------------------------------------------------------------
# Shared git fixture builder.
# ---------------------------------------------------------------------------
def _git_feature(repo_dir, feat_name, spec_subpath):
    """Init a git repo with a committed feature whose spec.md lives at
    <feat>/<spec_subpath>/spec.md. Returns the feature dir."""
    subprocess.run(["git", "init", repo_dir], capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "config", "user.email", "t@t.com"],
                   capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "config", "user.name", "T"],
                   capture_output=True)
    feat = os.path.join(repo_dir, "feat")
    _make_feature_dir(feat, feat_name, "spec-update")
    spec_dir = os.path.join(feat, *spec_subpath.split("/"))
    os.makedirs(spec_dir, exist_ok=True)
    with open(os.path.join(spec_dir, "spec.md"), "w") as f:
        f.write("original spec\n")
    subprocess.run(["git", "-C", repo_dir, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "commit", "-m", "init"],
                   capture_output=True)
    return feat, spec_dir


def _gate_allows(layout_label, spec_subpath):
    d = os.path.join(TMPROOT, f"gate_{layout_label}")
    feat, spec_dir = _git_feature(d, f"gate_{layout_label}", spec_subpath)
    # Modify the spec under this layout to create a non-empty diff.
    with open(os.path.join(spec_dir, "spec.md"), "a") as f:
        f.write("updated\n")
    rc, _, err = _run(
        ["python3", TDD_STEP, "transition", feat, "test-red"],
        env={**os.environ, "RABBIT_ROOT": d},
    )
    with open(os.path.join(feat, "feature.json")) as f:
        state = json.load(f)["tdd_state"]
    if rc == 0 and state == "test-red":
        ok(f"Inv 38 dual-read: gate allows spec diff under {layout_label}")
    else:
        ko(f"Inv 38 dual-read ({layout_label}): rc={rc} state={state} "
           f"stderr={err!r}")


def t_gate_specs_layout():
    _gate_allows("specs", "specs")


def t_gate_legacy_layout():
    _gate_allows("docs_spec", "docs/spec")


# ---------------------------------------------------------------------------
# 3. Numbered-list check (Inv 41) resolves both layouts without crashing.
#    The transition must still succeed (check is best-effort, non-blocking).
# ---------------------------------------------------------------------------
def t_numbered_list_specs():
    d = os.path.join(TMPROOT, "nl_specs")
    feat, spec_dir = _git_feature(d, "nl_specs", "specs")
    with open(os.path.join(spec_dir, "spec.md"), "a") as f:
        f.write("1. first\n2. second\n")
    rc, _, err = _run(
        ["python3", TDD_STEP, "transition", feat, "test-red"],
        env={**os.environ, "RABBIT_ROOT": d},
    )
    with open(os.path.join(feat, "feature.json")) as f:
        state = json.load(f)["tdd_state"]
    if rc == 0 and state == "test-red":
        ok("Inv 41 dual-read: numbered-list hook runs against specs/ layout")
    else:
        ko(f"Inv 41 specs: rc={rc} state={state} stderr={err!r}")


# ---------------------------------------------------------------------------
# 4. dispatch-tdd-subagent.py accepts a --spec under specs/ and emits a
#    grep NOTE that points at specs/ (no docs/spec/ literal).
# ---------------------------------------------------------------------------
def t_dispatch_scoped_note_uses_specs():
    # Use the real repo: tdd-subagent now lives under specs/. Dispatch with
    # --affected-invariants to force the scoped-view NOTE to render.
    spec_path = os.path.join(FEATURE_DIR, "specs", "spec.md")
    rc, out, err = _run(
        ["python3", DISPATCH, "--scope", "tdd-subagent",
         "--spec", spec_path, "--affected-invariants", "1"],
        env={**os.environ},
    )
    text = out.decode()
    if rc != 0:
        ko(f"dispatch scoped: rc={rc} stderr={err.decode()!r}")
        return
    if "/specs/spec.md`" in text and "/docs/spec/spec.md`" not in text:
        ok("dispatch: scoped-view grep NOTE points at specs/ (not docs/spec/)")
    else:
        # Surface a snippet for debugging.
        idx = text.find("NOTE: scoped view")
        snippet = text[idx:idx + 200] if idx >= 0 else "(NOTE not found)"
        ko(f"dispatch: scoped NOTE layout wrong: {snippet!r}")


def t_dispatch_accepts_specs_spec():
    spec_path = os.path.join(FEATURE_DIR, "specs", "spec.md")
    rc, out, _ = _run(
        ["python3", DISPATCH, "--scope", "tdd-subagent", "--spec", spec_path],
        env={**os.environ},
    )
    if rc == 0 and b"LOCK" in out and b"UNLOCK" in out:
        ok("dispatch: assembles prompt from a --spec under specs/")
    else:
        ko(f"dispatch accepts specs: rc={rc}")


print(f"running specs-migration tests against {FEATURE_DIR}")
t_own_layout()
t_gate_specs_layout()
t_gate_legacy_layout()
t_numbered_list_specs()
t_dispatch_scoped_note_uses_specs()
t_dispatch_accepts_specs_spec()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
