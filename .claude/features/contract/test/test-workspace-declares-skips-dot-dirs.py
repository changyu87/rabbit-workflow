#!/usr/bin/env python3
"""test-workspace-declares-skips-dot-dirs.py — Inv 24 (issue #1150).

Regression for the false-RED where a transient dot-prefixed directory under
`.claude/features/` (e.g. `.pytest_cache`, created when another feature's
pytest suite runs) was counted by `test-workspace-declares-all-features.py`
as an undeclared feature, turning the contract repo gate RED falsely.

Real feature directories never carry a leading dot. Inv 24 requires the gate
to exclude dot-prefixed entries from the on-disk feature set.

  t1: the production script `test-workspace-declares-all-features.py` filters
      dot-prefixed directories — it does NOT add a dot-prefixed dir to the
      on-disk feature set (source-level guard present).
  t2 (E2E): with a transient `.pytest_cache` dot-dir physically present under
      the REAL `.claude/features/`, the production gate still PASSES (exits 0).
      Before the fix this exited 1 with `.pytest_cache` reported as undeclared.

Non-interactive. Exits non-zero on any failure.
"""

import os
import sys
import shutil
import subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
PROD_SCRIPT = os.path.join(TEST_DIR, "test-workspace-declares-all-features.py")

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True,
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
FEATURES_DIR = os.path.join(REPO_ROOT, ".claude/features")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: the production script carries a dot-prefix filter on the on-disk set.
with open(PROD_SCRIPT, encoding="utf-8") as f:
    src = f.read()
if "startswith(\".\")" in src or "startswith('.')" in src:
    ok("t1", "production script filters dot-prefixed entries from on-disk set")
else:
    ko("t1", "production script does NOT filter dot-prefixed entries (Inv 24)")

# t2 (E2E): a transient dot-dir under the real .claude/features/ must not
# false-RED the production gate.
dot_dir = os.path.join(FEATURES_DIR, ".pytest_cache")
created = False
if not os.path.isdir(dot_dir):
    os.makedirs(dot_dir, exist_ok=True)
    created = True
try:
    res = subprocess.run(
        ["python3", PROD_SCRIPT], capture_output=True, text=True,
    )
    if res.returncode == 0:
        ok("t2", "gate PASSES with transient .pytest_cache dot-dir present")
    else:
        ko("t2", f"gate RED with .pytest_cache present (exit {res.returncode}):\n"
                 f"{res.stdout}\n{res.stderr}")
finally:
    if created:
        shutil.rmtree(dot_dir, ignore_errors=True)

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
