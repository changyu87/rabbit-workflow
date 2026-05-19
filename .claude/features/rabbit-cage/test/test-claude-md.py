#!/usr/bin/env python3
"""rabbit-cage CLAUDE.md @-import tests."""
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CLAUDE_MD = os.path.join(REPO_ROOT, "CLAUDE.md")

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


def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


print("test-claude-md.py")

content = read_file(CLAUDE_MD)

# t1: no @-import to .claude/philosophy.md flat path
if not re.search(r"@.*\.claude/philosophy\.md", content):
    ok(1, "CLAUDE.md does not @-import .claude/philosophy.md")
else:
    fail_t(1, "CLAUDE.md still @-imports .claude/philosophy.md (stale flat path)")

# t2: no @-import to work-guide.md
if not re.search(r"@.*work-guide\.md", content):
    ok(2, "CLAUDE.md does not @-import work-guide.md")
else:
    fail_t(2, "CLAUDE.md still @-imports work-guide.md")

# t3: no inline policy marker
if "rabbit-policy-start" not in content:
    ok(3, "CLAUDE.md does not contain rabbit-policy-start marker (pure @-import pointer)")
else:
    fail_t(3, "CLAUDE.md still contains rabbit-policy-start marker (inline content not removed)")

# t4: @-imports point to .claude/features/policy/
if re.search(r"^@\.claude/features/policy/", content, re.MULTILINE):
    ok(4, "CLAUDE.md contains @-imports pointing to .claude/features/policy/")
else:
    fail_t(4, "CLAUDE.md does not contain @-imports to .claude/features/policy/")

# t5: .claude/philosophy.md does NOT exist
if not os.path.isfile(os.path.join(REPO_ROOT, ".claude/philosophy.md")):
    ok(5, ".claude/philosophy.md does not exist (removed)")
else:
    fail_t(5, ".claude/philosophy.md still exists (not yet removed)")

# t6: .claude/work-guide.md does NOT exist
if not os.path.isfile(os.path.join(REPO_ROOT, ".claude/work-guide.md")):
    ok(6, ".claude/work-guide.md does not exist (removed)")
else:
    fail_t(6, ".claude/work-guide.md still exists (not yet removed)")

# t7: contains "Feature-oriented" (new structured header per Inv 10a)
if "Feature-oriented" in content:
    ok(7, "CLAUDE.md contains 'Feature-oriented'")
else:
    fail_t(7, "CLAUDE.md does not contain 'Feature-oriented' (header missing trait)")

# t8: does NOT contain "two source-of-truth"
if "two source-of-truth" not in content:
    ok(8, "CLAUDE.md does not contain old phrase 'two source-of-truth'")
else:
    fail_t(8, "CLAUDE.md still contains old phrase 'two source-of-truth' (not yet removed)")

# t9: run.py has at least 9 suite invocations
run_py = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/test/run.py")
run_content = read_file(run_py)
suite_count = len(re.findall(r'^\s*"test-[a-zA-Z0-9_-]+\.py"', run_content, re.MULTILINE))
if suite_count >= 9:
    ok(9, "run.py has at least 9 suite invocations")
else:
    fail_t(9, f"run.py has only {suite_count} suite invocations — expected >= 9")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
