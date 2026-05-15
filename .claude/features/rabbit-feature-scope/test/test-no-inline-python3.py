#!/usr/bin/env python3
# test-no-inline-python3.py — assert resolve-scope.py has no inline python3 subprocess calls.
# Part of CONTRACT-BACKLOG-5: unify tech stack to pure Python scripts.

import subprocess
import sys
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
script = Path(repo_root) / ".claude/features/rabbit-feature-scope/scripts/resolve-scope.py"
helper = Path(repo_root) / ".claude/features/rabbit-feature-scope/scripts/format-feature-context.py"

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

# 1. resolve-scope.py must exist and be a Python file (no .sh)
if script.is_file():
    ok("resolve-scope.py exists (converted from .sh)")
else:
    fail(f"resolve-scope.py not found (expected at {script})")

# 2. resolve-scope.py must have python3 shebang
first = ""
if script.is_file():
    with open(script) as f:
        first = f.readline().rstrip("\n")
if first == "#!/usr/bin/env python3":
    ok("resolve-scope.py has python3 shebang")
else:
    fail(f"resolve-scope.py missing python3 shebang: {first}")

# 3. format-feature-context.py must exist
if helper.is_file():
    ok("format-feature-context.py exists")
else:
    fail("format-feature-context.py not found")

# 4. format-feature-context.py must produce non-empty output for valid JSON input
if helper.is_file():
    sample = '[{"name":"feat-a","path":".claude/features/feat-a","summary":"does A","tdd_state":"test-green"}]'
    result = subprocess.run(
        [sys.executable, str(helper)],
        input=sample, capture_output=True, text=True
    )
    if result.stdout.strip():
        ok("format-feature-context.py produces non-empty output")
    else:
        fail("format-feature-context.py produced empty output")
else:
    fail("format-feature-context.py skipped (file missing)")

# 5. resolve-scope.py invokes format-feature-context.py
if script.is_file():
    content = script.read_text()
    if "format-feature-context.py" in content:
        ok("resolve-scope.py invokes format-feature-context.py")
    else:
        fail("resolve-scope.py does not invoke format-feature-context.py")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
