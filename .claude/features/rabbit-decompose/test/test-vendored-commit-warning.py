#!/usr/bin/env python3
"""test-vendored-commit-warning.py — vendored-mode commit-the-scaffold warning.

End-to-end test of rabbit-decompose's mode-aware `vendored_commit_warning`
(spec Invariant 11; issue #1140).

Problem (#1140): in vendored/plugin mode, `rabbit-feature-touch`'s create-branch
step runs the TDD subagent inside a per-session git worktree branched from the
host repo's HEAD, and a worktree contains only COMMITTED files. rabbit-decompose
scaffolds feature dirs + seeds specs under
`.rabbit/rabbit-project/features/<name>/` but never commits them, so a
freshly-decomposed feature is INVISIBLE to a feature-touch worktree until it is
committed. Nothing in the decompose path warned the user that a commit is
required first.

Fix: `scripts/handoff-scaffold.py`'s Step 4 plan JSON (the `--features` run and
the `--plan-only` dry run) carries a deterministic, mode-aware
`vendored_commit_warning` field — a non-empty string in vendored mode, `null`
in standalone mode — and the `SKILL.md` Report step surfaces the instruction in
vendored mode.

This test asserts, end-to-end:

  1. Against a temp PLUGIN tree, `--plan-only` JSON carries
     `vendored_commit_warning` as a non-empty string that names the commit
     requirement and cites `worktree` and HEAD and `rabbit-feature-touch`.
  2. Against a temp STANDALONE tree, the same field is `null` (None).
  3. The warning is `detect_mode`-driven: toggling the plugin signature flips
     the field between a string and null.
  4. The `SKILL.md` Report step surfaces the vendored commit-the-scaffold
     instruction (names `rabbit-feature-touch` and a commit requirement in a
     vendored/plugin-specific way).

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when Step 4 scaffold hand-off is provided natively by
    the rabbit CLI, retiring the companion handoff-scaffold.py script.
"""
import json
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts", "handoff-scaffold.py")
SKILL_MD = os.path.join(FEATURE_DIR, "skills", "rabbit-decompose", "SKILL.md")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _write_features_file(d, features):
    path = os.path.join(d, "accepted.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(features, f)
    return path


def _run_plan(rabbit_root, features_file, workdir):
    proc = subprocess.run(
        [sys.executable, SCRIPT,
         "--features", features_file,
         "--rabbit-root", rabbit_root,
         "--plan-only"],
        capture_output=True, text=True, cwd=workdir,
    )
    if proc.returncode != 0:
        fail(f"handoff-scaffold.py --plan-only exited {proc.returncode}; "
             f"stderr:\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"--plan-only did not emit JSON: {e}; stdout:\n{proc.stdout}")


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
    fail(f"missing handoff-scaffold.py: {SCRIPT}")
if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")

FEATURES = [
    {"name": "feature-one", "globs": ["src/one/**/*"]},
    {"name": "feature-two", "globs": ["src/two/**/*"]},
]


# --- Check 1: plugin tree carries a non-empty, descriptive warning ----------
with tempfile.TemporaryDirectory() as td:
    feats = _write_features_file(td, FEATURES)

    plugin_root = _make_plugin_tree(td)
    plan = _run_plan(plugin_root, feats, td)

    if "vendored_commit_warning" not in plan:
        fail("plugin tree: plan JSON has no 'vendored_commit_warning' field")
    warn = plan.get("vendored_commit_warning")
    if not isinstance(warn, str) or not warn.strip():
        fail("plugin tree: vendored_commit_warning must be a non-empty string, "
             f"got {warn!r}")
    low = warn.lower()
    # The warning must name the commit requirement and the worktree/HEAD reason
    # and point at rabbit-feature-touch.
    if "commit" not in low:
        fail("plugin tree: warning does not mention committing the scaffold; "
             f"got {warn!r}")
    if "rabbit-feature-touch" not in low:
        fail("plugin tree: warning does not name rabbit-feature-touch; "
             f"got {warn!r}")
    if "worktree" not in low:
        fail("plugin tree: warning does not cite the worktree reason; "
             f"got {warn!r}")
    if "head" not in low:
        fail("plugin tree: warning does not cite the HEAD-only-sees-committed "
             f"reason; got {warn!r}")

    # --- Check 2: standalone tree -> null ----------------------------------
    standalone_root = _make_standalone_tree(td)
    plan_s = _run_plan(standalone_root, feats, td)
    if "vendored_commit_warning" not in plan_s:
        fail("standalone tree: plan JSON has no 'vendored_commit_warning' field")
    if plan_s.get("vendored_commit_warning") is not None:
        fail("standalone tree: vendored_commit_warning must be null in "
             f"standalone mode, got {plan_s.get('vendored_commit_warning')!r}")


# --- Check 3: detect_mode-driven (toggle flips the field) -------------------
with tempfile.TemporaryDirectory() as td2:
    feats2 = _write_features_file(td2, FEATURES)
    plugin_root = _make_plugin_tree(td2)
    p1 = _run_plan(plugin_root, feats2, td2)
    # Same .rabbit basename but parent has NO non-.rabbit sibling -> standalone.
    lone_parent = os.path.join(td2, "lone")
    os.makedirs(lone_parent)
    lone_rabbit = os.path.join(lone_parent, ".rabbit")
    os.makedirs(lone_rabbit)
    p2 = _run_plan(lone_rabbit, feats2, td2)
    if not isinstance(p1.get("vendored_commit_warning"), str):
        fail("toggle: plugin signature did not yield a string warning")
    if p2.get("vendored_commit_warning") is not None:
        fail("toggle: removing the plugin signature did not null the warning")


# --- Check 4: SKILL.md Report step surfaces the vendored instruction --------
with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

# Locate the Report step (final sub-step of the Step 4 hand-off), anchored by
# content not letter. The body must surface a commit-the-scaffold instruction
# that names rabbit-feature-touch and the vendored/plugin context.
if "vendored_commit_warning" not in skill_text:
    fail("SKILL.md Report step does not surface the script-emitted "
         "vendored_commit_warning")
if "rabbit-feature-touch" not in skill_text:
    fail("SKILL.md does not name rabbit-feature-touch in the Report step")
# Must be mode-aware (vendored/plugin-specific).
sl = skill_text.lower()
if "vendored" not in sl and "plugin" not in sl:
    fail("SKILL.md commit-the-scaffold instruction is not vendored/plugin-aware")
if "commit" not in sl:
    fail("SKILL.md Report step does not mention committing the scaffold")

print("All checks passed.")
