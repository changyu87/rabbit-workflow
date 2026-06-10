#!/usr/bin/env python3
"""test-vendored-commit-warning.py — vendored-mode commit-the-scaffold warning.

End-to-end test of rabbit-decompose's Step 8 (Report) mode-aware
commit-the-scaffold warning.

In vendored/plugin mode, `rabbit-feature-touch` create-branch runs the TDD
subagent inside a per-session git worktree branched from the host repo's HEAD.
A worktree contains only COMMITTED files. rabbit-decompose scaffolds feature
dirs and seeds specs under `.rabbit/rabbit-project/features/<name>/` but never
commits them. Immediately after a greenfield decompose, running feature-touch
on a freshly-decomposed feature creates a worktree that does NOT contain the
feature dir, so the TDD subagent has nothing to implement.

The in-scope fix surfaces a DETERMINISTIC, mode-aware warning from the script
that emits the Step-4 scaffold/report plan JSON (`handoff-scaffold.py`): a
`vendored_commit_warning` field, non-empty in vendored/plugin mode and null in
standalone mode, instructing the user to COMMIT the scaffolded
`.rabbit/rabbit-project/features/<name>/` dirs and seeded specs to the user
repo BEFORE running `rabbit-feature-touch` (because feature-touch's worktree
branches from HEAD and only sees committed files). The SKILL.md Report step
(Step 8) reflects the same warning.

This test asserts, end-to-end:

  1. Against a temp PLUGIN tree, the script's `--plan-only` JSON carries a
     NON-EMPTY `vendored_commit_warning` string that mentions committing the
     scaffold, names `rabbit-feature-touch`, and explains the worktree/HEAD
     reason.
  2. Against a temp STANDALONE tree, the `vendored_commit_warning` field is
     ABSENT or null (the warning is vendored-only — standalone has no
     HEAD-based worktree problem).
  3. The mode decision is `detect_mode`-driven: toggling the plugin signature
     flips whether the warning is emitted.
  4. The SKILL.md Step 8 (Report) body reflects the same vendored
     commit-the-scaffold instruction: it names `rabbit-feature-touch`, the
     commit requirement, and the worktree/HEAD-only-sees-committed reason.

Run non-interactively. Exits non-zero on failure.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature-touch's worktree natively includes
    uncommitted .rabbit scaffold, removing the need for the commit warning.
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
        plan = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"--plan-only did not emit JSON: {e}; stdout:\n{proc.stdout}")
    # Clean up any authored batch file so the test is hermetic.
    bf = plan.get("batch_file")
    if bf and os.path.isfile(bf):
        try:
            os.unlink(bf)
        except OSError:
            pass
    return plan


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


def _make_lone_rabbit_tree(parent):
    """A `.rabbit` dir whose parent has NO non-.rabbit sibling -> standalone."""
    lone = os.path.join(parent, "lone")
    os.makedirs(lone)
    rabbit_root = os.path.join(lone, ".rabbit")
    os.makedirs(rabbit_root)
    return rabbit_root


if not os.path.isfile(SCRIPT):
    fail(f"missing orchestrator script: {SCRIPT}")
if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")

FEATURES = [
    {"name": "feature-one", "globs": ["src/one/**/*"]},
    {"name": "feature-two", "globs": ["src/two/**/*"]},
]

# --- Check 1: PLUGIN tree emits a non-empty vendored_commit_warning ----------
with tempfile.TemporaryDirectory() as td:
    feats = _write_features_file(td, FEATURES)

    plugin_root = _make_plugin_tree(td)
    plan = _run_plan(plugin_root, feats, td)
    if "vendored_commit_warning" not in plan:
        fail("plugin tree: --plan-only JSON carries no 'vendored_commit_warning'"
             f" field; got keys {sorted(plan.keys())!r}")
    warning = plan.get("vendored_commit_warning")
    if not warning or not isinstance(warning, str):
        fail("plugin tree: 'vendored_commit_warning' must be a NON-EMPTY string "
             f"in vendored mode; got {warning!r}")
    low = warning.lower()
    if "commit" not in low:
        fail("plugin tree: vendored_commit_warning does not mention committing "
             f"the scaffold; got {warning!r}")
    if "rabbit-feature-touch" not in low:
        fail("plugin tree: vendored_commit_warning does not name "
             f"rabbit-feature-touch; got {warning!r}")
    if "worktree" not in low:
        fail("plugin tree: vendored_commit_warning does not explain the "
             f"worktree reason; got {warning!r}")

    # --- Check 2: STANDALONE tree -> warning absent or null ------------------
    standalone_root = _make_standalone_tree(td)
    plan_s = _run_plan(standalone_root, feats, td)
    if plan_s.get("mode") != "standalone":
        fail(f"standalone tree: expected mode 'standalone', got "
             f"{plan_s.get('mode')!r}")
    s_warn = plan_s.get("vendored_commit_warning")
    if s_warn:
        fail("standalone tree: vendored_commit_warning must be absent/null "
             f"(no HEAD-based worktree problem in standalone); got {s_warn!r}")

# --- Check 3: detect_mode-driven toggle -------------------------------------
with tempfile.TemporaryDirectory() as td2:
    feats2 = _write_features_file(td2, FEATURES)
    plugin_root = _make_plugin_tree(td2)
    p1 = _run_plan(plugin_root, feats2, td2)
    lone_rabbit = _make_lone_rabbit_tree(td2)
    p2 = _run_plan(lone_rabbit, feats2, td2)
    if not p1.get("vendored_commit_warning"):
        fail("toggle: plugin-signature tree emitted no vendored_commit_warning")
    if p2.get("vendored_commit_warning"):
        fail("toggle: lone-.rabbit (standalone) tree emitted a "
             f"vendored_commit_warning; got {p2.get('vendored_commit_warning')!r}")

# --- Check 4: SKILL.md Step 8 (Report) reflects the warning ------------------
with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

# Isolate the Step 8 (Report) section body: from the `### Step 8` heading to the
# next `##`/`###` heading (or EOF).
m = re.search(r"(?ms)^###\s+Step\s+8\s+—\s+Report\b(.*?)(?=^\#\#|\Z)", skill_text)
if not m:
    fail("SKILL.md has no '### Step 8 — Report' section to carry the warning")
report_body = m.group(1)
rlow = report_body.lower()
if "rabbit-feature-touch" not in rlow:
    fail("SKILL.md Step 8 (Report) does not name rabbit-feature-touch in the "
         "commit-the-scaffold instruction")
if "commit" not in rlow:
    fail("SKILL.md Step 8 (Report) does not instruct committing the scaffold "
         "before feature-touch")
if "worktree" not in rlow:
    fail("SKILL.md Step 8 (Report) does not explain the worktree/HEAD reason "
         "for the commit requirement")
# The warning is mode-aware: vendored/plugin mode is the scenario.
if "vendored" not in rlow and "plugin" not in rlow:
    fail("SKILL.md Step 8 (Report) does not scope the commit warning to "
         "vendored/plugin mode")

print("All checks passed.")
