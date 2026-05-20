#!/usr/bin/env python3
"""rabbit-cage BACKLOG-22 dead code cleanup regression tests.

Verifies the cleanups specified in the BACKLOG-22 impl-suggestion:
  1) workspace-tree.py: legacy 2-arg form removed; .sh KEY_FILES branch
     removed (Inv 39 forbids .sh); ANNOTATIONS / STRUCTURAL_DIRS include
     the live post-consolidation features (rabbit-feature,
     tdd-state-machine).
  2) scope-guard.py: walk_up_find for .rabbit-scope-active collapsed to
     a direct repo-root file check.
  3) sync-check.py: counter-init no longer writes "0\\n" to disk when
     the counter file is missing — it initializes to 0 in-memory.
  4) install.py: usage() no longer re-parses __file__ to print docstring.
  5) commands/rabbit-project.md: self-reference 'init → rabbit-project.py'
     bullet removed (loop pointing the same script at itself).
"""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
WORKSPACE_TREE = os.path.join(CAGE, "scripts/workspace-tree.py")
SCOPE_GUARD = os.path.join(CAGE, "hooks/scope-guard.py")
SYNC_CHECK = os.path.join(CAGE, "hooks/sync-check.py")
INSTALL_PY = os.path.join(CAGE, "install.py")
PROJECT_MD = os.path.join(CAGE, "commands/rabbit-project.md")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


def read(p):
    with open(p) as f:
        return f.read()


print("test-RABBIT-CAGE-BACKLOG-22-cleanup.py")
print()

# ---- (1) workspace-tree.py ----
wt = read(WORKSPACE_TREE)

# t1 — legacy 2-arg form removed (no '<repo_root> <0|1>' branch).
if "Legacy" not in wt and 'args[1] in ("0", "1")' not in wt:
    ok(1, "workspace-tree.py: legacy 2-arg form removed from _resolve_args")
else:
    fail_t(1, "workspace-tree.py: legacy 2-arg form still present")

# t2 — .sh KEY_FILES branch removed (Inv 39 forbids .sh in rabbit-cage).
if 'name.endswith(".sh")' not in wt:
    ok(2, "workspace-tree.py: .sh key-file branch removed from is_key_file")
else:
    fail_t(2, "workspace-tree.py: .sh key-file branch still present")

# t3 — new feature names appear in ANNOTATIONS or STRUCTURAL_DIRS so they
#       render annotated in the structural view.
for feat in ("rabbit-feature", "tdd-state-machine"):
    if feat in wt:
        ok(f"3-{feat}", f"workspace-tree.py: '{feat}' annotated/structured")
    else:
        fail_t(f"3-{feat}", f"workspace-tree.py: '{feat}' missing from annotations/structural dirs")

# t4 — runtime smoke: structural view runs without traceback on this repo.
res = subprocess.run(
    [sys.executable, WORKSPACE_TREE, REPO_ROOT],
    capture_output=True, text=True,
)
if res.returncode == 0 and "rabbit-cage" in res.stdout:
    ok(4, "workspace-tree.py: structural view executes and includes rabbit-cage")
else:
    fail_t(4, f"workspace-tree.py: smoke failed (rc={res.returncode}, stderr={res.stderr!r})")

# t5 — --full flag still parses cleanly.
res2 = subprocess.run(
    [sys.executable, WORKSPACE_TREE, REPO_ROOT, "--full"],
    capture_output=True, text=True,
)
if res2.returncode == 0:
    ok(5, "workspace-tree.py: --full flag still accepted")
else:
    fail_t(5, f"workspace-tree.py: --full failed (rc={res2.returncode}, stderr={res2.stderr!r})")

# ---- (2) scope-guard.py ----
sg = read(SCOPE_GUARD)

# t6 — walk_up_find for the global scope marker collapsed into a direct
#       repo-root check. The global active-marker is only meaningful at the
#       repo root, so walking the ancestor chain is wasted work.
if 'walk_up_find(abs_path, ".rabbit-scope-active")' not in sg:
    ok(6, "scope-guard.py: walk_up_find for .rabbit-scope-active removed")
else:
    fail_t(6, "scope-guard.py: walk_up_find for .rabbit-scope-active still present")

# t7 — replacement is a direct REPO_ROOT / '.rabbit-scope-active' check.
if "REPO_ROOT / \".rabbit-scope-active\"" in sg or \
   "REPO_ROOT / '.rabbit-scope-active'" in sg:
    ok(7, "scope-guard.py: direct repo-root .rabbit-scope-active check in place")
else:
    fail_t(7, "scope-guard.py: no direct REPO_ROOT/.rabbit-scope-active check")

# ---- (3) sync-check.py ----
sc = read(SYNC_CHECK)

# t8 — counter-init no longer writes "0\n" to disk on first read.
if 'counter_file.write_text("0\\n")\n    try:' not in sc and \
   'if not counter_file.exists():\n        counter_file.write_text("0\\n")' not in sc:
    ok(8, "sync-check.py: counter-init no longer writes '0\\n' on missing file")
else:
    fail_t(8, "sync-check.py: counter-init still writes '0\\n' on missing file")

# ---- (4) install.py ----
ip = read(INSTALL_PY)

# t9 — usage() no longer re-parses __file__ to extract banner.
if "open(__file__)" not in ip:
    ok(9, "install.py: usage() no longer re-parses __file__")
else:
    fail_t(9, "install.py: usage() still re-parses __file__ to extract banner")

# t10 — install.py --help still produces helpful output (smoke).
res3 = subprocess.run(
    [sys.executable, INSTALL_PY, "--help"],
    capture_output=True, text=True,
)
if res3.returncode == 0 and "install.py" in (res3.stdout + res3.stderr):
    ok(10, "install.py --help: prints usage and exits 0")
else:
    fail_t(10, f"install.py --help broken (rc={res3.returncode})")

# ---- (5) commands/rabbit-project.md ----
pm = read(PROJECT_MD)

# t11 — the self-reference bullet 'init → rabbit-project.py' is removed.
#       The remaining bullets target the per-subcommand scripts; pointing
#       'init' back at the same dispatch script is a documentation loop.
#       Detect the exact buggy bullet shape: a list item whose key is
#       `init` and whose target is the same rabbit-project.py dispatch
#       script. Prose mentioning 'init' in the surrounding paragraph is
#       acceptable.
import re as _re
if not _re.search(
    r"^[\-\*]\s+`init`\s*→\s*`.*rabbit-project\.py`",
    pm,
    _re.MULTILINE,
):
    ok(11, "rabbit-project.md: 'init → rabbit-project.py' self-reference bullet removed")
else:
    fail_t(11, "rabbit-project.md: 'init → rabbit-project.py' self-reference bullet still present")

# t12 — Inv 67: rabbit-project.md MUST reference only .py scripts under
#       .claude/features/rabbit-cage/scripts/, no .sh / stale paths.
if ".sh" not in pm:
    ok(12, "rabbit-project.md: no .sh references (Inv 67)")
else:
    fail_t(12, "rabbit-project.md: contains .sh reference (Inv 67 violation)")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
