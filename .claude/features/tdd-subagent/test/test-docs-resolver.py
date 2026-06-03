#!/usr/bin/env python3
# test-docs-resolver.py — issue #399 Phase 2a (tdd-subagent) coverage.
#
# End-to-end coverage for the flat docs/ spec-path resolver in
# tdd-subagent's owned tooling (tdd-step.py, dispatch-tdd-subagent.py).
#
# Target layout (#399): a feature's spec/contract live at the FLAT
# docs/spec.md and docs/contract.md (siblings of docs/bugs/), with the
# legacy specs/spec.md / specs/contract.md retained during the coexistence
# window. Resolution PREFERS docs/, FALLS BACK to specs/.
#
# Behaviours under test:
#   1. resolve_spec_path returns docs/<name> when present.
#   2. resolve_spec_path falls back to specs/<name> when only that exists.
#   3. docs/<name> wins when BOTH exist.
#   4. Behaviour holds for spec.md AND contract.md.
#   5. The spec-update -> test-red git-diff gate accepts a change under the
#      FLAT docs/ layout (a docs/spec.md edit).
#   6. The numbered-list check resolves the flat docs/ layout without
#      crashing (transition still succeeds, best-effort).
#   7. dispatch-tdd-subagent.py accepts a --spec under docs/ and assembles
#      a prompt; the scoped-view grep NOTE points at the docs/ path.
#
# Owner: rabbit-workflow team (tdd-subagent)
# Deprecation criterion: when issue #399 Phase 3 drops the specs/ fallback
#     (the fallback assertions retire then).
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TDD_STEP = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")
DISPATCH = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
TMPROOT = tempfile.mkdtemp()

sys.path.insert(0, SCRIPT_DIR)
from state_machine_helpers import make_feature_dir as _make_feature_dir  # noqa: E402

# Import the resolver helper directly from tdd-step.py as a module.
_spec = importlib.util.spec_from_file_location("tdd_step_mod", TDD_STEP)
_tdd_step = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tdd_step)

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


def _mk(feat_dir, layouts, name):
    """Create <feat_dir>/<layout>/<name> for each layout in `layouts`."""
    for layout in layouts:
        d = os.path.join(feat_dir, layout)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w") as f:
            f.write(f"{layout} {name}\n")


# ---------------------------------------------------------------------------
# 1-4. resolve_spec_path: prefer docs/, fall back to specs/, for both files.
# ---------------------------------------------------------------------------
def t_resolver_docs_only():
    for name in ("spec.md", "contract.md"):
        d = os.path.join(TMPROOT, f"docs_only_{name}")
        _mk(d, ["docs"], name)
        got = _tdd_step.resolve_spec_path(d, name)
        want = os.path.join(d, "docs", name)
        if got == want:
            ok(f"resolver: docs/{name} returned when only docs/ present")
        else:
            ko(f"resolver docs-only {name}: got {got!r} want {want!r}")


def t_resolver_specs_fallback():
    for name in ("spec.md", "contract.md"):
        d = os.path.join(TMPROOT, f"specs_only_{name}")
        _mk(d, ["specs"], name)
        got = _tdd_step.resolve_spec_path(d, name)
        want = os.path.join(d, "specs", name)
        if got == want:
            ok(f"resolver: falls back to specs/{name} when only specs/ present")
        else:
            ko(f"resolver specs-fallback {name}: got {got!r} want {want!r}")


def t_resolver_docs_wins():
    for name in ("spec.md", "contract.md"):
        d = os.path.join(TMPROOT, f"both_{name}")
        _mk(d, ["docs", "specs"], name)
        got = _tdd_step.resolve_spec_path(d, name)
        want = os.path.join(d, "docs", name)
        if got == want:
            ok(f"resolver: docs/{name} wins when both layouts present")
        else:
            ko(f"resolver both {name}: got {got!r} want {want!r}")


def t_resolver_neither():
    # When neither exists, the specs/ candidate is returned (canonical
    # fallback for downstream existence-check error messages).
    d = os.path.join(TMPROOT, "neither")
    os.makedirs(d, exist_ok=True)
    got = _tdd_step.resolve_spec_path(d, "spec.md")
    want = os.path.join(d, "specs", "spec.md")
    if got == want:
        ok("resolver: returns specs/ candidate when neither layout present")
    else:
        ko(f"resolver neither: got {got!r} want {want!r}")


# ---------------------------------------------------------------------------
# Shared git fixture builder (flat-docs-aware).
# ---------------------------------------------------------------------------
def _git_feature(repo_dir, feat_name, spec_rel):
    """Init a git repo with a committed feature whose spec.md lives at
    <feat>/<spec_rel>/spec.md. Returns (feat_dir, spec_dir)."""
    subprocess.run(["git", "init", repo_dir], capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "config", "user.email", "t@t.com"],
                   capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "config", "user.name", "T"],
                   capture_output=True)
    feat = os.path.join(repo_dir, "feat")
    _make_feature_dir(feat, feat_name, "spec-update")
    spec_dir = os.path.join(feat, *spec_rel.split("/"))
    os.makedirs(spec_dir, exist_ok=True)
    with open(os.path.join(spec_dir, "spec.md"), "w") as f:
        f.write("original spec\n")
    subprocess.run(["git", "-C", repo_dir, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "commit", "-m", "init"],
                   capture_output=True)
    return feat, spec_dir


# ---------------------------------------------------------------------------
# 5. git-diff gate accepts a spec edit under the FLAT docs/ layout.
# ---------------------------------------------------------------------------
def t_gate_flat_docs_layout():
    d = os.path.join(TMPROOT, "gate_flat_docs")
    feat, spec_dir = _git_feature(d, "gate_flat_docs", "docs")
    with open(os.path.join(spec_dir, "spec.md"), "a") as f:
        f.write("updated\n")
    rc, _, err = _run(
        ["python3", TDD_STEP, "transition", feat, "test-red"],
        env={**os.environ, "RABBIT_ROOT": d},
    )
    with open(os.path.join(feat, "feature.json")) as f:
        state = json.load(f)["tdd_state"]
    if rc == 0 and state == "test-red":
        ok("gate flat-docs: allows spec diff under docs/spec.md")
    else:
        ko(f"gate flat-docs: rc={rc} state={state} stderr={err!r}")


# ---------------------------------------------------------------------------
# 6. numbered-list check resolves the flat docs/ layout (no crash).
# ---------------------------------------------------------------------------
def t_numbered_list_flat_docs():
    d = os.path.join(TMPROOT, "nl_flat_docs")
    feat, spec_dir = _git_feature(d, "nl_flat_docs", "docs")
    with open(os.path.join(spec_dir, "spec.md"), "a") as f:
        f.write("1. first\n2. second\n")
    rc, _, err = _run(
        ["python3", TDD_STEP, "transition", feat, "test-red"],
        env={**os.environ, "RABBIT_ROOT": d},
    )
    with open(os.path.join(feat, "feature.json")) as f:
        state = json.load(f)["tdd_state"]
    if rc == 0 and state == "test-red":
        ok("numbered-list flat-docs: hook runs against docs/ layout")
    else:
        ko(f"numbered-list flat-docs: rc={rc} state={state} stderr={err!r}")


# ---------------------------------------------------------------------------
# 7. dispatch accepts a --spec under docs/ and the scoped grep NOTE points
#    at the docs/ path (the actual --spec path, not a specs/ literal).
# ---------------------------------------------------------------------------
def t_dispatch_accepts_docs_spec():
    repo = os.path.join(TMPROOT, "dispatch_repo")
    feat_parent = os.path.join(repo, ".claude", "features", "demo")
    real_root = os.path.abspath(
        os.path.join(FEATURE_DIR, "..", "..", ".."))
    os.makedirs(os.path.join(repo, ".claude", "features"), exist_ok=True)
    for dep in ("contract", "tdd-subagent", "policy"):
        os.symlink(
            os.path.join(real_root, ".claude", "features", dep),
            os.path.join(repo, ".claude", "features", dep),
        )
    _make_feature_dir(feat_parent, "demo", "spec-update")
    docs = os.path.join(feat_parent, "docs")
    os.makedirs(docs, exist_ok=True)
    spec_path = os.path.join(docs, "spec.md")
    with open(spec_path, "w") as f:
        f.write("## Invariants\n\n1. **First.** body one\n\n"
                "2. **Second.** body two\n")
    rc, out, err = _run(
        ["python3", DISPATCH, "--scope", "demo", "--spec", spec_path],
        env={**os.environ, "RABBIT_ROOT": repo},
    )
    if rc == 0 and b"LOCK" in out and b"UNLOCK" in out:
        ok("dispatch: assembles prompt from a --spec under docs/")
    else:
        ko(f"dispatch accepts docs spec: rc={rc} stderr={err.decode()!r}")
        return
    rc2, out2, err2 = _run(
        ["python3", DISPATCH, "--scope", "demo", "--spec", spec_path,
         "--affected-invariants", "1"],
        env={**os.environ, "RABBIT_ROOT": repo},
    )
    text = out2.decode()
    if rc2 == 0 and "/docs/spec.md`" in text:
        ok("dispatch: scoped-view grep NOTE points at docs/spec.md")
    else:
        idx = text.find("NOTE: scoped view")
        snippet = text[idx:idx + 200] if idx >= 0 else "(NOTE not found)"
        ko(f"dispatch scoped NOTE flat-docs: rc={rc2} snippet={snippet!r} "
           f"stderr={err2.decode()!r}")


print(f"running docs-resolver tests against {FEATURE_DIR}")
t_resolver_docs_only()
t_resolver_specs_fallback()
t_resolver_docs_wins()
t_resolver_neither()
t_gate_flat_docs_layout()
t_numbered_list_flat_docs()
t_dispatch_accepts_docs_spec()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
