#!/usr/bin/env python3
# test-no-inline-python3.py — assert resolve-scope.py has no inline python3 subprocess calls.
# Part of CONTRACT-BACKLOG-5: unify tech stack to pure Python scripts.
#
# Strengthened in RABBIT-FEATURE-SCOPE-BUG-29: previously the test only checked
# shebang and existence; it never verified the actual Inv 7 enforcement
# contract (no inline `python3 -c` or python3 heredocs in resolve-scope.py).
# Now greps the source for forbidden patterns directly.

import re
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

# ---------------------------------------------------------------------------
# BUG-29 / Inv 7 enforcement: grep resolve-scope.py source for forbidden
# inline-python3 patterns. This is the contract the test name claims to
# enforce; the prior version only checked shebang.
# ---------------------------------------------------------------------------
if script.is_file():
    src = script.read_text()

    # Forbidden pattern 1: `python3 -c` invocations (any spacing).
    if re.search(r"python3\s+-c\b", src):
        fail("Inv 7: resolve-scope.py contains 'python3 -c' inline invocation")
    else:
        ok("Inv 7: no 'python3 -c' inline invocation in resolve-scope.py")

    # Forbidden pattern 2: python3 heredoc — `python3 ... <<` where the
    # heredoc body would be inline Python source. Match `python3` followed
    # by anything on the same line that contains `<<` (heredoc operator).
    heredoc_lines = [
        line for line in src.splitlines()
        if re.search(r"\bpython3\b", line) and "<<" in line
    ]
    if heredoc_lines:
        fail(f"Inv 7: python3 heredoc construct found in resolve-scope.py: {heredoc_lines}")
    else:
        ok("Inv 7: no python3 heredoc constructs in resolve-scope.py")

    # Forbidden pattern 3: subprocess args list of form ["python3", "-c", ...]
    # (would also be caught by pattern 1, but explicit here for clarity).
    if re.search(r"['\"]python3['\"]\s*,\s*['\"]-c['\"]", src):
        fail("Inv 7: subprocess call with ['python3', '-c', ...] found")
    else:
        ok("Inv 7: no subprocess ['python3', '-c', ...] pattern in resolve-scope.py")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
