#!/usr/bin/env python3
"""test-step1-source-root.py — Step 1 source-root resolution guard (#901).

End-to-end test of rabbit-decompose's Step 1 (Gather inputs) source-root
resolution. In plugin mode the cwd / rabbit-root is the vendored `.rabbit/`
install dir, but the project to DECOMPOSE is its PARENT
(`rabbit_root.parent`) — matching scaffold-feature.py._detect_plugin_mode
(project_root = rabbit_root.parent). Without guidance a no-args plugin-mode
run could point Glob/Read at the `.rabbit` tooling itself and "decompose" the
workflow instead of the user project.

The fix folds the SOURCE-ROOT resolution into the canonical
`scripts/handoff-scaffold.py` resolver (the one #890 introduced for Step 4,
reusing `rabbit-meta.lib.mode_detection.detect_mode`), so Step 1 and Step 4
AGREE on a single deterministic resolver instead of the model hand-resolving
an ambiguous `<repo>`.

This test asserts, end-to-end:

  1. `handoff-scaffold.py --source-root --rabbit-root <plugin>` resolves the
     decomposition source root to the PARENT of the `.rabbit` install (the
     user project), and against a STANDALONE tree resolves it to the repo
     root itself.
  2. The resolution is detect_mode-driven (structural), not a hard-coded
     single mode-path read: toggling the plugin signature flips the resolved
     source root between parent-of-.rabbit and the root itself.
  3. The plan-only JSON output ALSO carries the same `source_root`, so Step 4
     and Step 1 share the one resolver.
  4. The SKILL.md Step 1 body references the canonical resolver and no longer
     hand-resolves an ambiguous `<repo>` source root in a live (non-example)
     bash block.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when Step 1 source-root resolution is provided
    natively by the rabbit CLI, retiring the companion handoff-scaffold.py
    resolver.
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


def _run_source_root(rabbit_root, workdir):
    """Run the script in --source-root mode, return parsed JSON."""
    proc = subprocess.run(
        [sys.executable, SCRIPT,
         "--source-root",
         "--rabbit-root", rabbit_root],
        capture_output=True, text=True, cwd=workdir,
    )
    if proc.returncode != 0:
        fail(f"handoff-scaffold.py --source-root exited {proc.returncode}; "
             f"stderr:\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail(f"--source-root did not emit JSON: {e}; stdout:\n{proc.stdout}")


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
    return json.loads(proc.stdout)


def _make_plugin_tree(parent):
    """A `.rabbit/` dir with a non-.rabbit sibling -> detect_mode == plugin."""
    host = os.path.join(parent, "host-project")
    os.makedirs(host)
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    os.makedirs(rabbit_root)
    return host, rabbit_root


def _make_standalone_tree(parent):
    """A dir NOT named `.rabbit` -> detect_mode == standalone."""
    root = os.path.join(parent, "standalone-root")
    os.makedirs(root)
    return root


if not os.path.isfile(SCRIPT):
    fail(f"missing orchestrator script: {SCRIPT}")
if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")


def _realpath(p):
    return os.path.realpath(p)


# --- Check 1: plugin -> parent-of-.rabbit; standalone -> root itself --------
with tempfile.TemporaryDirectory() as td:
    host, plugin_root = _make_plugin_tree(td)
    res = _run_source_root(plugin_root, td)
    if res.get("mode") != "plugin":
        fail(f"plugin tree: expected mode 'plugin', got {res.get('mode')!r}")
    got = res.get("source_root")
    if not got:
        fail("plugin tree: --source-root did not report a source_root")
    if _realpath(got) != _realpath(host):
        fail("plugin tree: source_root must be the PARENT of the .rabbit "
             f"install ({host!r}), got {got!r}")

    standalone_root = _make_standalone_tree(td)
    res_s = _run_source_root(standalone_root, td)
    if res_s.get("mode") != "standalone":
        fail(f"standalone tree: expected mode 'standalone', got "
             f"{res_s.get('mode')!r}")
    got_s = res_s.get("source_root")
    if _realpath(got_s) != _realpath(standalone_root):
        fail("standalone tree: source_root must be the repo root itself "
             f"({standalone_root!r}), got {got_s!r}")

# --- Check 2: detect_mode-driven (toggling signature flips source root) ------
with tempfile.TemporaryDirectory() as td2:
    host, plugin_root = _make_plugin_tree(td2)
    p1 = _run_source_root(plugin_root, td2)
    # Same `.rabbit` basename but parent has NO non-.rabbit sibling -> standalone.
    lone_parent = os.path.join(td2, "lone")
    os.makedirs(lone_parent)
    lone_rabbit = os.path.join(lone_parent, ".rabbit")
    os.makedirs(lone_rabbit)
    p2 = _run_source_root(lone_rabbit, td2)
    if p1.get("mode") != "plugin" or p2.get("mode") != "standalone":
        fail("source-root resolution is not detect_mode-driven: toggling the "
             f"plugin signature did not flip the mode (got {p1.get('mode')!r}, "
             f"{p2.get('mode')!r})")
    # plugin source root = parent (host); standalone source root = root itself.
    if _realpath(p1.get("source_root")) != _realpath(host):
        fail("plugin source_root not parent-of-.rabbit after toggle")
    if _realpath(p2.get("source_root")) != _realpath(lone_rabbit):
        fail("standalone source_root not the root itself after toggle")

# --- Check 3: plan-only JSON carries the same source_root -------------------
with tempfile.TemporaryDirectory() as td3:
    feats = _write_features_file(td3, [{"name": "f-one", "globs": ["a/**"]}])
    host, plugin_root = _make_plugin_tree(td3)
    plan = _run_plan(plugin_root, feats, td3)
    if "source_root" not in plan:
        fail("plan-only JSON does not carry source_root (Step 1 + Step 4 must "
             "share one resolver)")
    if _realpath(plan.get("source_root")) != _realpath(host):
        fail("plan-only source_root must be parent-of-.rabbit in plugin mode, "
             f"got {plan.get('source_root')!r}")

# --- Check 4: SKILL.md Step 1 references the resolver, drops <repo> ---------
with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

if "handoff-scaffold.py" not in skill_text:
    fail("SKILL.md does not reference handoff-scaffold.py")

# Isolate the Step 1 section (from its heading to the next "### Step" heading).
m = re.search(r"(?ms)^###\s+Step\s+1\b.*?(?=^###\s+Step\s+2\b)", skill_text)
if not m:
    fail("could not locate Step 1 section in SKILL.md")
step1 = m.group(0)

# Step 1 must reference the canonical resolver for the source root.
if "handoff-scaffold.py" not in step1 and "--source-root" not in step1:
    fail("SKILL.md Step 1 does not reference the canonical source-root "
         "resolver (handoff-scaffold.py / --source-root)")

# Step 1 must mention the plugin-mode parent-of-.rabbit source root.
if not re.search(r"parent of the `?\.rabbit`?", step1, re.IGNORECASE):
    fail("SKILL.md Step 1 does not state the plugin-mode source root is the "
         "parent of the .rabbit install")

# No live (non-example) bash block in Step 1 may hand-resolve an ambiguous
# <repo> placeholder. Marked <!-- example --> blocks are illustrative and
# exempt (mirrors check-script-backed.py).
_FENCE = re.compile(r"(?ms)^[ \t]*```(?:bash|sh|shell)[^\n]*\n(.*?)^[ \t]*```")
_PLACEHOLDER = re.compile(r"<[a-z][a-z0-9._-]*>")
_EXAMPLE_MARKER = re.compile(r"(?i)^<!--\s*example\b[^>]*-->\s*$")


def _is_marked_example(text, fence_start):
    preceding = text[:fence_start].rstrip("\n")
    if not preceding:
        return False
    prev_line = preceding.rsplit("\n", 1)[-1].strip()
    return bool(_EXAMPLE_MARKER.match(prev_line))


# Scan within the full text but only flag fences that fall inside Step 1.
step1_start = m.start()
step1_end = m.end()
for fm in _FENCE.finditer(skill_text):
    if not (step1_start <= fm.start() < step1_end):
        continue
    if _is_marked_example(skill_text, fm.start()):
        continue
    block = fm.group(1)
    if _PLACEHOLDER.search(block):
        line_no = skill_text.count("\n", 0, fm.start()) + 1
        fail(f"SKILL.md Step 1 still hand-resolves an ambiguous placeholder in "
             f"a live bash block at line {line_no}: "
             f"{block.strip().splitlines()[0]!r}")

print("All checks passed.")
