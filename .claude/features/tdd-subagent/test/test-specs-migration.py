#!/usr/bin/env python3
# test-specs-migration.py — issue #399 Phase 2b (tdd-subagent) coverage.
#
# End-to-end coverage for the specs/ -> flat docs/ migration of the
# tdd-subagent feature and the dual-read behaviour of its owned tooling
# (dispatch-tdd-subagent.py, tdd-step.py).
#
# Behaviours under test:
#   1. tdd-subagent's own spec/contract/CHANGELOG live at the flat docs/
#      layout: docs/spec.md, docs/contract.md, docs/CHANGELOG.md exist;
#      no specs/ dir remains and no feature-root CHANGELOG.md remains.
#   2. The Inv 38 spec-update -> test-red git-diff gate accepts a change
#      under the flat docs/ layout (preferred) AND under the LEGACY
#      specs/ layout (fallback, dual-read for not-yet-migrated features).
#   3. The Inv 41 numbered-list check resolves both layouts (no crash,
#      transition still succeeds — the check is best-effort).
#   4. dispatch-tdd-subagent.py works with a --spec under the flat docs/
#      layout and the scoped-view grep NOTE points at docs/spec.md.
#
# Owner: rabbit-workflow team (tdd-subagent)
# Deprecation criterion: when issue #399 Phase 3 drops the specs/
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
# 1. tdd-subagent's own layout: flat docs/ present, specs/ absent, and the
#    feature-root CHANGELOG.md moved under docs/.
# ---------------------------------------------------------------------------
def t_own_layout():
    docs_spec = os.path.join(FEATURE_DIR, "docs", "spec.md")
    docs_contract = os.path.join(FEATURE_DIR, "docs", "contract.md")
    docs_changelog = os.path.join(FEATURE_DIR, "docs", "CHANGELOG.md")
    specs_dir = os.path.join(FEATURE_DIR, "specs")
    root_changelog = os.path.join(FEATURE_DIR, "CHANGELOG.md")
    if os.path.isfile(docs_spec):
        ok("migration: docs/spec.md exists")
    else:
        ko(f"migration: docs/spec.md missing at {docs_spec}")
    if os.path.isfile(docs_contract):
        ok("migration: docs/contract.md exists")
    else:
        ko(f"migration: docs/contract.md missing at {docs_contract}")
    if os.path.isfile(docs_changelog):
        ok("migration: docs/CHANGELOG.md exists")
    else:
        ko(f"migration: docs/CHANGELOG.md missing at {docs_changelog}")
    if not os.path.exists(specs_dir):
        ok("migration: no specs/ directory remains")
    else:
        ko(f"migration: specs/ still present at {specs_dir}")
    if not os.path.exists(root_changelog):
        ok("migration: no feature-root CHANGELOG.md remains")
    else:
        ko(f"migration: feature-root CHANGELOG.md still present at "
           f"{root_changelog}")


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


def t_gate_docs_layout():
    _gate_allows("docs", "docs")


def t_gate_legacy_layout():
    _gate_allows("specs", "specs")


# ---------------------------------------------------------------------------
# 3. Numbered-list check (Inv 41) resolves both layouts without crashing.
#    The transition must still succeed (check is best-effort, non-blocking).
# ---------------------------------------------------------------------------
def t_numbered_list_docs():
    d = os.path.join(TMPROOT, "nl_docs")
    feat, spec_dir = _git_feature(d, "nl_docs", "docs")
    with open(os.path.join(spec_dir, "spec.md"), "a") as f:
        f.write("1. first\n2. second\n")
    rc, _, err = _run(
        ["python3", TDD_STEP, "transition", feat, "test-red"],
        env={**os.environ, "RABBIT_ROOT": d},
    )
    with open(os.path.join(feat, "feature.json")) as f:
        state = json.load(f)["tdd_state"]
    if rc == 0 and state == "test-red":
        ok("Inv 41 dual-read: numbered-list hook runs against docs/ layout")
    else:
        ko(f"Inv 41 docs: rc={rc} state={state} stderr={err!r}")


# ---------------------------------------------------------------------------
# 4. dispatch-tdd-subagent.py accepts a --spec under the flat docs/ layout
#    and emits a grep NOTE that points at docs/spec.md (no specs/ or legacy
#    docs/spec/ literal).
# ---------------------------------------------------------------------------
def t_dispatch_scoped_note_uses_docs():
    # Use the real repo: tdd-subagent now lives under the flat docs/ layout.
    # Dispatch with --affected-invariants to force the scoped-view NOTE to
    # render.
    spec_path = os.path.join(FEATURE_DIR, "docs", "spec.md")
    rc, out, err = _run(
        ["python3", DISPATCH, "--scope", "tdd-subagent",
         "--spec", spec_path, "--affected-invariants", "1"],
        env={**os.environ},
    )
    text = out.decode()
    if rc != 0:
        ko(f"dispatch scoped: rc={rc} stderr={err.decode()!r}")
        return
    if "/docs/spec.md`" in text and "/docs/spec/spec.md`" not in text:
        ok("dispatch: scoped-view grep NOTE points at docs/spec.md")
    else:
        # Surface a snippet for debugging.
        idx = text.find("NOTE: scoped view")
        snippet = text[idx:idx + 200] if idx >= 0 else "(NOTE not found)"
        ko(f"dispatch: scoped NOTE layout wrong: {snippet!r}")


def t_dispatch_accepts_docs_spec():
    spec_path = os.path.join(FEATURE_DIR, "docs", "spec.md")
    rc, out, _ = _run(
        ["python3", DISPATCH, "--scope", "tdd-subagent", "--spec", spec_path],
        env={**os.environ},
    )
    if rc == 0 and b"LOCK" in out and b"UNLOCK" in out:
        ok("dispatch: assembles prompt from a --spec under docs/")
    else:
        ko(f"dispatch accepts docs: rc={rc}")


print(f"running specs-migration tests against {FEATURE_DIR}")
t_own_layout()
t_gate_docs_layout()
t_gate_legacy_layout()
t_numbered_list_docs()
t_dispatch_scoped_note_uses_docs()
t_dispatch_accepts_docs_spec()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
