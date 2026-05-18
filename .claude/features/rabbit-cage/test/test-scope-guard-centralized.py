#!/usr/bin/env python3
"""rabbit-cage: scope-guard centralized path allowlist tests."""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")
RUN_PY = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/test/run.py")
TEST_CLAUDE_MD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/test/test-claude-md.py")

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


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


print("test-scope-guard-centralized.py")

sg = read(SCOPE_GUARD)
run = read(RUN_PY)
tcm = read(TEST_CLAUDE_MD)

# t1 (BUG-55: assert the literal path-prefix '/.claude/bugs/', not just the
# bare token 'bugs', which would also match unrelated comments)
if "/.claude/bugs/" in sg:
    ok(1, "scope-guard.py contains literal '/.claude/bugs/' path-prefix")
else:
    fail_t(1, "scope-guard.py does NOT contain a literal '/.claude/bugs/' path-prefix")

# t2 (BUG-55: same tightening for backlogs)
if "/.claude/backlogs/" in sg:
    ok(2, "scope-guard.py contains literal '/.claude/backlogs/' path-prefix")
else:
    fail_t(2, "scope-guard.py does NOT contain a literal '/.claude/backlogs/' path-prefix")

# t3
if "test-backlog-e2e-tdd" not in run:
    ok(3, "run.py does not contain test-backlog-e2e-tdd (suite removed)")
else:
    fail_t(3, "run.py still contains test-backlog-e2e-tdd (not yet removed)")

# t4
if "test-backlog-e2e-tdd" not in tcm:
    ok(4, "test-claude-md.py does not reference test-backlog-e2e-tdd at all (old t9 removed)")
else:
    fail_t(4, "test-claude-md.py still references test-backlog-e2e-tdd (old t9 positive assertion not yet removed)")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
