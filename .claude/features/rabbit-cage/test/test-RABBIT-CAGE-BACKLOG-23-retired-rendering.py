#!/usr/bin/env python3
"""E2E test for RABBIT-CAGE-BACKLOG-23: workspace-tree.py renders retired
features with a [RETIRED] tag (driven by feature.json `status` == 'retired').
"""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
WORKSPACE_TREE = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/scripts/workspace-tree.py"
)

failures = 0


def ok(t, msg):
    print(f"  PASS t{t}: {msg}")


def fail_t(t, msg):
    global failures
    print(f"  FAIL t{t}: {msg}")
    failures += 1


print("test-RABBIT-CAGE-BACKLOG-23-retired-rendering.py")
print()

# Run workspace-tree.py in structural mode (default).
result = subprocess.run(
    [sys.executable, WORKSPACE_TREE], capture_output=True, text=True
)
if result.returncode != 0:
    fail_t(0, f"workspace-tree.py exited non-zero: {result.stderr}")
    print()
    print(f"Results: 0 passed, {failures} failed")
    sys.exit(1)

out = result.stdout

# t1: rabbit-feature-scope is retired (per feature.json) and its tree entry
# must include the [RETIRED] tag.
matching = [
    ln for ln in out.splitlines()
    if "rabbit-feature-scope/" in ln
]
if matching and any("[RETIRED]" in ln for ln in matching):
    ok(1, "rabbit-feature-scope directory entry carries [RETIRED] tag")
else:
    fail_t(
        1,
        "rabbit-feature-scope is retired in feature.json but workspace-tree "
        "output does not carry [RETIRED] tag. Matching lines: "
        + repr(matching),
    )

# t2: rabbit-spec is retired and must also carry [RETIRED] tag.
matching = [
    ln for ln in out.splitlines()
    if "rabbit-spec/" in ln
]
if matching and any("[RETIRED]" in ln for ln in matching):
    ok(2, "rabbit-spec directory entry carries [RETIRED] tag")
else:
    fail_t(
        2,
        "rabbit-spec is retired in feature.json but workspace-tree "
        "output does not carry [RETIRED] tag. Matching lines: "
        + repr(matching),
    )

# t3: Active features (e.g. rabbit-cage itself) MUST NOT carry the
# [RETIRED] tag.
matching = [
    ln for ln in out.splitlines()
    if "rabbit-cage/" in ln and "[RETIRED]" in ln
]
if not matching:
    ok(3, "active feature rabbit-cage does not carry [RETIRED] tag")
else:
    fail_t(
        3,
        "active feature rabbit-cage incorrectly carries [RETIRED] tag: "
        + repr(matching),
    )

# t4: rabbit-cage spec.md mentions the retired-rendering invariant so the
# behaviour is discoverable from the spec, not just the script.
spec_path = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md"
)
with open(spec_path) as f:
    spec_src = f.read()
if "[RETIRED]" in spec_src and "workspace-tree" in spec_src:
    ok(4, "spec.md documents the [RETIRED] tag for workspace-tree.py")
else:
    fail_t(
        4,
        "spec.md does not document the [RETIRED] tag for workspace-tree.py — "
        "behaviour is undocumented",
    )

print()
print(f"Results: {4 - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
