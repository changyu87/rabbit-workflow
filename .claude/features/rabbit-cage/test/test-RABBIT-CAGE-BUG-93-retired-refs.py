#!/usr/bin/env python3
"""rabbit-cage BUG-93 — post-consolidation reference cleanup.

Verifies that the rabbit-cage surface no longer references the retired
features `rabbit-spec` and `rabbit-feature-scope` as live skills, and that
references that name a real script path are updated to the current
post-consolidation topology (`rabbit-feature-spec` skill, `tdd-state-machine`
feature for `tdd-step.py`).

Scope: this regression test pins the workspace-tree.py annotations, the
rabbit-cage README script-path references, the spec.md narrative references
to the spec-authoring skill, and the BACKLOG-22/BACKLOG-18 test fixtures
that enumerate the retired feature names.

The retired features keep their physical directories (status=retired in
feature.json) so this test does NOT touch the .claude/features/<X>/
filesystem entries themselves — it asserts only that the rabbit-cage
surface does not advertise them as live.
"""
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
WORKSPACE_TREE = os.path.join(CAGE, "scripts/workspace-tree.py")
README = os.path.join(CAGE, "README.md")
SPEC = os.path.join(CAGE, "docs/spec/spec.md")
BACKLOG22 = os.path.join(CAGE, "test/test-RABBIT-CAGE-BACKLOG-22-cleanup.py")
SYNC_AGG = os.path.join(
    CAGE, "test/test-RABBIT-CAGE-BACKLOG-18-sync-check-aggregation.py"
)

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


print("test-RABBIT-CAGE-BUG-93-retired-refs.py")
print()

# ---- workspace-tree.py ----
wt = read(WORKSPACE_TREE)

# t1 — retired feature names are no longer listed as live annotations.
if "rabbit-feature-scope" not in wt:
    ok(1, "workspace-tree.py: 'rabbit-feature-scope' annotation removed")
else:
    fail_t(1, "workspace-tree.py: still annotates retired 'rabbit-feature-scope'")

if "rabbit-spec" not in wt:
    ok(2, "workspace-tree.py: 'rabbit-spec' annotation removed")
else:
    fail_t(2, "workspace-tree.py: still annotates retired 'rabbit-spec'")

# t3 — the current TDD-state-machine feature IS annotated (replaces the
#       stale tdd-subagent annotation key that pointed at tdd-step.py).
if "tdd-state-machine" in wt:
    ok(3, "workspace-tree.py: 'tdd-state-machine' present in annotations/structural set")
else:
    fail_t(3, "workspace-tree.py: 'tdd-state-machine' missing")

# t4 — smoke: structural view still runs without traceback on this repo.
res = subprocess.run(
    [sys.executable, WORKSPACE_TREE, REPO_ROOT],
    capture_output=True, text=True,
)
if res.returncode == 0 and "rabbit-cage" in res.stdout:
    ok(4, "workspace-tree.py: structural view executes and renders rabbit-cage")
else:
    fail_t(4, f"workspace-tree.py: smoke failed rc={res.returncode} stderr={res.stderr!r}")

# ---- README.md ----
readme = read(README)

# t5 — the example `tdd-step.py` script path points at tdd-state-machine,
#       not the stale tdd-subagent path.
if ".claude/features/tdd-state-machine/scripts/tdd-step.py" in readme:
    ok(5, "README.md: tdd-step.py path points at tdd-state-machine")
else:
    fail_t(5, "README.md: tdd-step.py path not updated to tdd-state-machine")

if ".claude/features/tdd-subagent/scripts/tdd-step.py" not in readme:
    ok(6, "README.md: stale tdd-subagent/scripts/tdd-step.py path removed")
else:
    fail_t(6, "README.md: stale tdd-subagent/scripts/tdd-step.py path still present")

# ---- spec.md ----
spec = read(SPEC)

# t7 — narrative references to the spec-authoring skill use the current
#       skill name `rabbit-feature-spec`, not retired `rabbit-spec`.
#       (Retirement-context mentions, e.g. "RETIRED ...", are not expected
#       in this spec; assert simple absence of bare `rabbit-spec`.)
if not re.search(r"\brabbit-spec\b", spec):
    ok(7, "spec.md: no live `rabbit-spec` references remain")
else:
    fail_t(7, "spec.md: still references retired skill `rabbit-spec`")

# t8 — current `rabbit-feature-spec` skill IS named in narrative.
if "rabbit-feature-spec" in spec:
    ok(8, "spec.md: references current `rabbit-feature-spec` skill")
else:
    fail_t(8, "spec.md: missing `rabbit-feature-spec` reference")

# ---- BACKLOG-22 cleanup test fixture ----
b22 = read(BACKLOG22)

# t9 — the BACKLOG-22 test no longer enumerates `rabbit-spec` /
#       `rabbit-feature-scope` as expected-live names (its own fixture
#       must reflect the post-consolidation topology).
if "rabbit-feature-scope" not in b22 and re.search(r"\brabbit-spec\b", b22) is None:
    ok(9, "test-RABBIT-CAGE-BACKLOG-22-cleanup.py: fixture purged of retired names")
else:
    fail_t(9, "test-RABBIT-CAGE-BACKLOG-22-cleanup.py: still references retired names")

# ---- BACKLOG-18 sync-check aggregation test fixture ----
b18 = read(SYNC_AGG)

# t10 — sample skill names written into `.rabbit-skills-updated` no longer
#        include retired `rabbit-spec`.
if re.search(r"\brabbit-spec\b", b18) is None:
    ok(10, "test-RABBIT-CAGE-BACKLOG-18-sync-check-aggregation.py: fixture purged of `rabbit-spec`")
else:
    fail_t(10, "test-RABBIT-CAGE-BACKLOG-18-sync-check-aggregation.py: still uses retired `rabbit-spec`")

print()
print(f"PASS: {pass_n}")
print(f"FAIL: {fail_n}")
sys.exit(0 if fail_n == 0 else 1)
