#!/usr/bin/env python3
# test-resolve-scope.py

import subprocess
import sys
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
script = Path(repo_root) / ".claude/features/rabbit-feature-scope/scripts/resolve-scope.py"
find_feature = Path(repo_root) / ".claude/features/contract/scripts/find-feature.py"

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1

def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1

# 1. script exists and is executable
if script.is_file() and script.stat().st_mode & 0o111:
    ok("script executable")
else:
    fail("not executable or missing")

# 2. exits 2 with no args
result = subprocess.run([sys.executable, str(script)], capture_output=True)
if result.returncode == 2:
    ok("exits 2 with no args")
else:
    fail(f"exit code no-args: {result.returncode}")

# 3. emits non-empty prompt for a request
result = subprocess.run(
    [sys.executable, str(script), "fix the scope guard bug"],
    capture_output=True, text=True
)
prompt = result.stdout
if prompt.strip():
    ok("emits non-empty prompt")
else:
    fail("empty prompt")

# 4. prompt includes EVERY feature name from find-feature.py list — not just
# the first (BUG-27: depending on "first feature" was brittle to ordering
# changes). The assertion now requires the full set to appear; if any feature
# is missing the prompt's REGISTERED FEATURES block is incomplete.
all_features = []
if find_feature.is_file():
    all_features = [
        line.strip() for line in subprocess.check_output(
            [sys.executable, str(find_feature), repo_root, "list"],
            text=True
        ).splitlines() if line.strip()
    ]
missing = [f for f in all_features if f not in prompt]
if all_features and not missing:
    ok(f"prompt includes all {len(all_features)} feature names from find-feature.py list")
else:
    fail(f"prompt missing features: {missing} (had {len(all_features)} total)")

# 5. prompt includes the request text verbatim
if "fix the scope guard bug" in prompt:
    ok("prompt includes request text")
else:
    fail("prompt missing request text")

# 6. prompt specifies the JSON response schema
if '"features"' in prompt:
    ok("prompt specifies JSON schema")
else:
    fail("prompt missing JSON schema")

# 7. prompt instructs single-line JSON output
if "single line" in prompt:
    ok("prompt says single-line JSON")
else:
    fail("prompt missing single-line instruction")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
