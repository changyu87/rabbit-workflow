#!/usr/bin/env python3
"""test-dispatch-script.py — spec-seeder Inv 2: dispatch script end-to-end.

Sets up a tmpdir with sample files, invokes dispatch-spec-seeder.py with a
glob matching them, and asserts:
  (i)   exit code 0
  (ii)  stdout contains a prompt-file path
  (iii) the prompt file exists and contains slot-substituted values
"""

import os
import subprocess
import sys
import tempfile

REPO_ROOT = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=False,
).stdout.strip()

DISPATCH = os.path.join(REPO_ROOT, ".claude/features/spec-seeder/scripts/dispatch-spec-seeder.py")

PASS = 0
FAIL = 0


def ok(n, m):
    global PASS
    print(f"  PASS {n}: {m}")
    PASS += 1


def fail_t(n, m):
    global FAIL
    print(f"  FAIL {n}: {m}", file=sys.stderr)
    FAIL += 1


with tempfile.TemporaryDirectory() as tmp:
    # Create sample files for the glob to match
    sample_dir = os.path.join(tmp, "src")
    os.makedirs(sample_dir)
    for name in ("alpha.py", "beta.py", "gamma.py"):
        with open(os.path.join(sample_dir, name), "w") as f:
            f.write(f"# {name}\n")

    # Run dispatch script from the tmpdir so the glob resolves files from there
    glob_arg = os.path.join(sample_dir, "*.py")
    result = subprocess.run(
        ["python3", DISPATCH, "--feature-name", "demo", "--paths", glob_arg],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )

    # t1: exit 0
    if result.returncode == 0:
        ok("t1", f"dispatch exit 0 (stdout={result.stdout.strip()[:80]!r})")
    else:
        fail_t("t1", f"exit {result.returncode}; stderr={result.stderr!r}")

    # t2: stdout is a path
    prompt_path = result.stdout.strip()
    if prompt_path and os.path.isfile(prompt_path):
        ok("t2", f"prompt file exists at {prompt_path}")
    else:
        fail_t("t2", f"stdout {prompt_path!r} is not a valid file path")
        print(f"\nResults: {PASS} passed, {FAIL} failed")
        sys.exit(1)

    # t3: prompt contains slot-substituted values
    with open(prompt_path) as f:
        body = f.read()
    if "demo" in body:
        ok("t3a", "prompt contains feature_name 'demo'")
    else:
        fail_t("t3a", "feature_name 'demo' missing from prompt")
    if "alpha.py" in body and "beta.py" in body and "gamma.py" in body:
        ok("t3b", "prompt contains all three resolved file paths")
    else:
        fail_t("t3b", "resolved file paths missing from prompt")
    if glob_arg in body:
        ok("t3c", "prompt contains the original glob in paths_globs slot")
    else:
        fail_t("t3c", f"original glob {glob_arg!r} missing from prompt")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
