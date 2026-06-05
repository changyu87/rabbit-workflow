#!/usr/bin/env python3
"""test-default-rabbit-root.py — default rabbit-root resolution guard (#906).

End-to-end test of rabbit-decompose's mode/source-root resolver
(`scripts/handoff-scaffold.py`) when `--rabbit-root` is NOT supplied — the
default invocation the `SKILL.md` Step 1 and Step 4 bash blocks actually use.

The bug (#906): `_default_rabbit_root()` returned
`git rev-parse --show-toplevel`. In a plugin install the vendored `.rabbit/`
dir lives INSIDE the user project's git repo, so the git toplevel is the
user-project root (the PARENT of `.rabbit`), whose basename is not `.rabbit`.
`detect_mode` returns `plugin` only when `basename(rabbit_root) == '.rabbit'`,
so the default invocation mis-detected plugin installs as `standalone` and the
scaffolder silently took the wrong (per-feature instead of plugin `--batch`)
branch.

The fix (issue option (a)): `_default_rabbit_root()` returns `os.getcwd()`.
In a rabbit session the cwd IS the mode-correct rabbit root — the `.rabbit/`
dir in plugin mode, the repo root in standalone mode.

This test asserts, end-to-end:

  1. `_default_rabbit_root()` returns the current working directory.
  2. Running the resolver WITHOUT `--rabbit-root` from a simulated plugin cwd
     (`.../.rabbit` INSIDE a git repo, the case the bug regressed) detects
     `plugin` and the batch branch.
  3. Running it WITHOUT `--rabbit-root` from a repo root detects `standalone`.
  4. The corrected default keeps the #901 source-root resolution correct:
     plugin source_root = parent-of-`.rabbit` (the project root).
  5. The `SKILL.md` Step 1 and Step 4 bash blocks invoke the resolver with NO
     `--rabbit-root` flag, relying on the cwd default.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when the default rabbit-root resolution is provided
    natively by the rabbit CLI, retiring the companion handoff-scaffold.py
    resolver.
"""
import importlib.util
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


def _realpath(p):
    return os.path.realpath(p)


def _load_module():
    spec = importlib.util.spec_from_file_location("handoff_scaffold", SCRIPT)
    if spec is None or spec.loader is None:
        fail(f"could not load module spec for {SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(args, workdir):
    """Run the resolver from workdir with no --rabbit-root; return parsed JSON."""
    proc = subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, cwd=workdir,
    )
    if proc.returncode != 0:
        fail(f"handoff-scaffold.py {args} exited {proc.returncode}; "
             f"stderr:\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"{args} did not emit JSON: {e}; stdout:\n{proc.stdout}")


def _make_plugin_git_tree(parent):
    """A user project that IS a git repo, with a vendored `.rabbit/` install
    inside it plus a non-.rabbit sibling so detect_mode == plugin. This is the
    exact shape the #906 bug regressed: the git toplevel is the PROJECT root
    (parent of .rabbit), not the .rabbit dir."""
    host = os.path.join(parent, "myproj")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    subprocess.run(["git", "init", "-q"], cwd=host, check=True)
    rabbit_root = os.path.join(host, ".rabbit")
    os.makedirs(rabbit_root)
    return host, rabbit_root


def _make_standalone_git_tree(parent):
    """A git repo root NOT named `.rabbit` -> detect_mode == standalone."""
    root = os.path.join(parent, "standalone-root")
    os.makedirs(root)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


if not os.path.isfile(SCRIPT):
    fail(f"missing orchestrator script: {SCRIPT}")
if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")


# --- Check 1: _default_rabbit_root() returns the cwd ------------------------
mod = _load_module()
with tempfile.TemporaryDirectory() as td:
    sub = os.path.join(td, "some-cwd")
    os.makedirs(sub)
    cwd0 = os.getcwd()
    try:
        os.chdir(sub)
        got = mod._default_rabbit_root()
    finally:
        os.chdir(cwd0)
    if _realpath(got) != _realpath(sub):
        fail("_default_rabbit_root() must return the cwd "
             f"({sub!r}), got {got!r}")


# --- Check 2: default (no --rabbit-root) from cwd=.rabbit -> plugin/batch ----
with tempfile.TemporaryDirectory() as td:
    host, plugin_root = _make_plugin_git_tree(td)
    # Run from cwd = the .rabbit dir, WITHOUT --rabbit-root.
    res = _run(["--source-root"], plugin_root)
    if res.get("mode") != "plugin":
        fail("default invocation from cwd=.rabbit (inside a git repo) must "
             f"detect mode 'plugin', got {res.get('mode')!r} — the git "
             "toplevel (parent of .rabbit) is the WRONG default")
    # The batch branch must be selected by the Step 4 plan from the same cwd.
    feats_dir = os.path.join(td, "feats")
    os.makedirs(feats_dir)
    feats = os.path.join(feats_dir, "accepted.json")
    with open(feats, "w", encoding="utf-8") as f:
        json.dump([{"name": "f-one", "globs": ["a/**"]}], f)
    plan = _run(["--features", feats, "--plan-only"], plugin_root)
    if plan.get("mode") != "plugin" or plan.get("branch") != "batch":
        fail("default --plan-only from cwd=.rabbit must select the plugin "
             f"batch branch, got mode={plan.get('mode')!r} "
             f"branch={plan.get('branch')!r}")


# --- Check 3: default (no --rabbit-root) from a repo root -> standalone ------
with tempfile.TemporaryDirectory() as td:
    standalone_root = _make_standalone_git_tree(td)
    res = _run(["--source-root"], standalone_root)
    if res.get("mode") != "standalone":
        fail("default invocation from a repo root must detect mode "
             f"'standalone', got {res.get('mode')!r}")


# --- Check 4: corrected default keeps #901 source_root correct --------------
with tempfile.TemporaryDirectory() as td:
    host, plugin_root = _make_plugin_git_tree(td)
    res = _run(["--source-root"], plugin_root)
    got = res.get("source_root")
    if not got:
        fail("default --source-root did not report a source_root")
    if _realpath(got) != _realpath(host):
        fail("with the corrected cwd default, plugin source_root must be the "
             f"PARENT of the .rabbit install ({host!r}), got {got!r}")


# --- Check 5: SKILL.md bash blocks invoke the resolver without --rabbit-root -
with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

# Every bash block that invokes handoff-scaffold.py must NOT pass --rabbit-root
# (it relies on the corrected cwd default).
_FENCE = re.compile(r"(?ms)^[ \t]*```(?:bash|sh|shell)[^\n]*\n(.*?)^[ \t]*```")
found_invocation = False
for fm in _FENCE.finditer(skill_text):
    block = fm.group(1)
    if "handoff-scaffold.py" not in block:
        continue
    found_invocation = True
    if "--rabbit-root" in block:
        line_no = skill_text.count("\n", 0, fm.start()) + 1
        fail("SKILL.md bash block invoking handoff-scaffold.py passes "
             f"--rabbit-root at line {line_no}; it MUST rely on the corrected "
             "cwd default per Invariant 7")
if not found_invocation:
    fail("SKILL.md has no bash block invoking handoff-scaffold.py")


print("All checks passed.")
