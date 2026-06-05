#!/usr/bin/env python3
"""test-step4-script-backed.py — Step 4 Script-Backed Orchestration guard.

End-to-end test of rabbit-decompose's Step 4 scaffold hand-off (spec
Invariant 5; spec-rules §4 Script-Backed Orchestration).

Before #890 the SKILL.md body did Step 4 inline: it read a single hard-coded
`<repo>/.rabbit/.runtime/mode` path, branched plugin-vs-standalone in prose,
and authored a `/tmp/decompose-batch-<ts>.json` file with a model-assembled
`<ts>`. That is prompt-tier, not script-tier. The fix moves the work into
`scripts/handoff-scaffold.py`, which:

  - resolves the rabbit root and detects mode by REUSING
    `rabbit-meta.lib.mode_detection.detect_mode` (no single hard-coded
    mode-path read);
  - authors the batch temp file with a SCRIPT-OWNED timestamp; and
  - dispatches on the mode-correct branch (plugin -> scaffold-feature.py
    --batch; standalone -> per-feature rabbit-feature-scaffold plan).

This test asserts, end-to-end:

  1. Against a temp PLUGIN tree (a `.rabbit/` dir with a host sibling), the
     script's `--plan-only` JSON reports mode "plugin", the batch branch, and
     writes a batch file whose path carries a numeric (script-owned)
     timestamp and whose JSON content is the accepted feature list. The same
     accepted list run against a temp STANDALONE tree reports mode
     "standalone" and the per-feature plan branch (no batch file).
  2. The script resolves mode by importing detect_mode from rabbit-meta:
     flipping the tree's plugin signature flips the detected mode, proving the
     decision is detect_mode-driven, not a single hard-coded mode-path read.
  3. The SKILL.md Step 4 body invokes the script and carries no prose
     mode-branch and no runtime-placeholder bash block (the §4 violation the
     fix removes).

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when Step 4 scaffold hand-off is provided natively by
    the rabbit CLI, retiring the companion handoff-scaffold.py script.
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
    """Run the script in --plan-only mode against rabbit_root, return parsed
    JSON. cwd is set to workdir so any cwd-based resolution is hermetic."""
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
    """A `.rabbit/` dir with a non-.rabbit sibling -> detect_mode == plugin."""
    host = os.path.join(parent, "host-project")
    os.makedirs(host)
    # a sibling file so the parent has an entry whose name != ".rabbit"
    open(os.path.join(host, "README.md"), "w").close()
    rabbit_root = os.path.join(host, ".rabbit")
    os.makedirs(rabbit_root)
    return rabbit_root


def _make_standalone_tree(parent):
    """A dir NOT named `.rabbit` -> detect_mode == standalone."""
    root = os.path.join(parent, "standalone-root")
    os.makedirs(root)
    return root


if not os.path.isfile(SCRIPT):
    fail(f"missing Step 4 orchestrator script: {SCRIPT}")
if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")

FEATURES = [
    {"name": "feature-one", "globs": ["src/one/**/*"]},
    {"name": "feature-two", "globs": ["src/two/**/*"]},
]

# --- Check 1 + 2: end-to-end mode-driven branching --------------------------
with tempfile.TemporaryDirectory() as td:
    feats = _write_features_file(td, FEATURES)

    # PLUGIN tree
    plugin_root = _make_plugin_tree(td)
    plan = _run_plan(plugin_root, feats, td)
    if plan.get("mode") != "plugin":
        fail(f"plugin tree: expected mode 'plugin', got {plan.get('mode')!r}")
    if plan.get("branch") != "batch":
        fail(f"plugin tree: expected branch 'batch', got {plan.get('branch')!r}")
    batch_file = plan.get("batch_file")
    if not batch_file:
        fail("plugin tree: --plan-only did not report a batch_file path")
    if not os.path.isfile(batch_file):
        fail(f"plugin tree: batch file not authored on disk: {batch_file}")
    # Script-owned timestamp: the filename carries a >=10-digit numeric run id
    # (epoch seconds or similar) authored by the script, not a placeholder.
    if not re.search(r"\d{10,}", os.path.basename(batch_file)):
        fail("plugin tree: batch file name carries no script-owned numeric "
             f"timestamp: {os.path.basename(batch_file)}")
    if "<ts>" in batch_file or "<" in batch_file:
        fail(f"plugin tree: batch file path carries a placeholder: {batch_file}")
    with open(batch_file, encoding="utf-8") as f:
        written = json.load(f)
    if written != FEATURES:
        fail("plugin tree: batch file content does not equal the accepted "
             f"feature list; got {written!r}")
    try:
        os.unlink(batch_file)
    except OSError:
        pass

    # STANDALONE tree — same accepted list, different mode signature.
    standalone_root = _make_standalone_tree(td)
    plan_s = _run_plan(standalone_root, feats, td)
    if plan_s.get("mode") != "standalone":
        fail(f"standalone tree: expected mode 'standalone', got "
             f"{plan_s.get('mode')!r}")
    if plan_s.get("branch") != "per-feature":
        fail(f"standalone tree: expected branch 'per-feature', got "
             f"{plan_s.get('branch')!r}")
    if plan_s.get("batch_file"):
        fail("standalone tree: batch form is plugin-only; no batch_file "
             f"should be authored, got {plan_s.get('batch_file')!r}")
    plan_features = plan_s.get("features") or []
    names = {fdict.get("name") for fdict in plan_features}
    if names != {"feature-one", "feature-two"}:
        fail("standalone tree: per-feature plan does not enumerate the "
             f"accepted features; got {names!r}")

# --- Check 2 (continued): same root, plugin signature toggled ---------------
# Prove the mode decision is detect_mode-driven (structural), not a hard-coded
# single mode-path read: a dir named `.rabbit` with a host sibling is plugin;
# remove the sibling-bearing parent property and it becomes standalone.
with tempfile.TemporaryDirectory() as td2:
    feats2 = _write_features_file(td2, FEATURES)
    # Plugin signature present.
    plugin_root = _make_plugin_tree(td2)
    p1 = _run_plan(plugin_root, feats2, td2)
    # Same .rabbit basename but parent has NO non-.rabbit sibling -> standalone.
    lone_parent = os.path.join(td2, "lone")
    os.makedirs(lone_parent)
    lone_rabbit = os.path.join(lone_parent, ".rabbit")
    os.makedirs(lone_rabbit)
    p2 = _run_plan(lone_rabbit, feats2, td2)
    if p1.get("mode") != "plugin" or p2.get("mode") != "standalone":
        fail("mode decision is not detect_mode-driven: toggling the plugin "
             f"signature did not flip the mode (got {p1.get('mode')!r}, "
             f"{p2.get('mode')!r})")
    for bf in (p1.get("batch_file"),):
        if bf and os.path.isfile(bf):
            os.unlink(bf)

# --- Check 3: SKILL.md Step 4 body is script-backed -------------------------
with open(SKILL_MD, encoding="utf-8") as f:
    skill_text = f.read()

# The body must invoke the companion script.
if "scripts/handoff-scaffold.py" not in skill_text:
    fail("SKILL.md does not invoke scripts/handoff-scaffold.py in Step 4")

# No runtime-placeholder bash block: scan every fenced bash block (including
# list-indented fences) for a runtime placeholder token like <ts> / <repo> /
# <feature-name> the model would assemble. An <!-- example -->-marked block is
# illustrative documentation and exempt (mirrors check-script-backed.py).
_FENCE = re.compile(
    r"(?ms)^[ \t]*```(?:bash|sh|shell)[^\n]*\n(.*?)^[ \t]*```",
)
_PLACEHOLDER = re.compile(r"<[a-z][a-z0-9._-]*>")
_EXAMPLE_MARKER = re.compile(r"(?i)^<!--\s*example\b[^>]*-->\s*$")
# A prose/shell mode-branch the model would execute.
_BRANCH = re.compile(r"(?m)^\s*(?:if|elif|case)\b")


def _is_marked_example(text, fence_start):
    preceding = text[:fence_start].rstrip("\n")
    if not preceding:
        return False
    prev_line = preceding.rsplit("\n", 1)[-1].strip()
    return bool(_EXAMPLE_MARKER.match(prev_line))


for m in _FENCE.finditer(skill_text):
    if _is_marked_example(skill_text, m.start()):
        continue
    block = m.group(1)
    line_no = skill_text.count("\n", 0, m.start()) + 1
    if _PLACEHOLDER.search(block):
        fail(f"SKILL.md Step 4 still carries a runtime-placeholder bash block "
             f"at line {line_no}: {block.strip().splitlines()[0]!r}")
    if _BRANCH.search(block):
        fail(f"SKILL.md still carries a shell mode-branch block at line "
             f"{line_no}: branching belongs in the companion script")

# No prose mode-branch: the body must not instruct the reader to detect mode
# and branch the scaffolder themselves. The canonical prose-branch phrasing
# the fix removes is a "Plugin mode" / "Standalone mode" decision the model
# executes inline. The script now owns that branch; the body may still mention
# the modes descriptively, but must not present the read-a-mode-file decision.
if re.search(r"[Dd]etect the mode from\s+<?repo>?[\s/.]*runtime/mode", skill_text):
    fail("SKILL.md Step 4 still tells the model to read a hard-coded "
         "<repo>/.rabbit/.runtime/mode path and branch (prose-tier)")

print("All checks passed.")
