#!/usr/bin/env python3
"""rabbit-cage generate-claude-md tests."""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
GENERATE_SCRIPT = os.path.join(CAGE_DIR, "scripts/generate-claude-md.py")
SYNC_HOOK = os.path.join(CAGE_DIR, "hooks/sync-check.py")
SETTINGS_JSON = os.path.join(REPO_ROOT, ".claude/settings.json")

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


print("test-generate-claude-md.py")

# t1
if os.path.isfile(GENERATE_SCRIPT) and os.access(GENERATE_SCRIPT, os.X_OK):
    ok(1, "generate-claude-md.py exists and is executable")
else:
    fail_t(1, "generate-claude-md.py missing or not executable")

# t2
if os.path.isfile(SYNC_HOOK) and os.access(SYNC_HOOK, os.X_OK):
    ok(2, "sync-check.py exists and is executable")
else:
    fail_t(2, "sync-check.py missing or not executable")

# t3
settings = read(SETTINGS_JSON)
if '"Stop"' in settings:
    ok(3, 'settings.json contains "Stop"')
else:
    fail_t(3, 'settings.json does not contain "Stop"')

# t4: gitignore does not have CLAUDE.md
gitignore = read(os.path.join(REPO_ROOT, ".gitignore"))
gitignore_lines = [line.strip() for line in gitignore.splitlines()]
if "CLAUDE.md" not in gitignore_lines:
    ok(4, ".gitignore does NOT contain CLAUDE.md (committed to git per BACKLOG-13)")
else:
    fail_t(4, ".gitignore still lists CLAUDE.md — must be removed so file can be committed")

# Run generate script
generated_output = ""
generate_ok = False
if os.access(GENERATE_SCRIPT, os.X_OK):
    result = subprocess.run([GENERATE_SCRIPT], capture_output=True, text=True)
    if result.returncode == 0:
        generated_output = result.stdout + result.stderr
        generate_ok = True

# t5
if generate_ok and "@.claude/features/policy/philosophy.md" in generated_output:
    ok(5, "output contains '@.claude/features/policy/philosophy.md'")
else:
    fail_t(5, "output does not contain '@.claude/features/policy/philosophy.md'" if generate_ok else "generate-claude-md.py missing or failed")

# t6
if generate_ok and "@.claude/features/policy/spec-rules.md" in generated_output:
    ok(6, "output contains '@.claude/features/policy/spec-rules.md'")
else:
    fail_t(6, "output does not contain '@.claude/features/policy/spec-rules.md'" if generate_ok else "generate-claude-md.py missing or failed")

# t7
if generate_ok and "@.claude/features/policy/coding-rules.md" in generated_output:
    ok(7, "output contains '@.claude/features/policy/coding-rules.md'")
else:
    fail_t(7, "output does not contain '@.claude/features/policy/coding-rules.md'" if generate_ok else "generate-claude-md.py missing or failed")

# t8
if generate_ok and "@./.claude/policy" not in generated_output:
    ok(8, "output does not contain '@./.claude/policy' (@-import lines absent)")
else:
    fail_t(8, "output still contains '@./.claude/policy' (@-import lines not expanded)" if generate_ok else "generate-claude-md.py missing or failed")

# t9: run.py contains test-generate-claude-md
run_py = read(os.path.join(CAGE_DIR, "test/run.py"))
if "test-generate-claude-md" in run_py:
    ok(9, "test-generate-claude-md is registered in run.py")
else:
    fail_t(9, "test-generate-claude-md is NOT registered in run.py")

# t10: policy-header.json valid JSON
policy_header_path = os.path.join(CAGE_DIR, "policy-header.json")
try:
    with open(policy_header_path) as f:
        ph = json.load(f)
    ok(10, "policy-header.json is valid JSON")
except Exception:
    ph = {}
    fail_t(10, "policy-header.json does not exist or is not valid JSON")

# t11: required fields
try:
    assert "header" in ph
    assert "version" in ph
    assert ph["header"].startswith("#")
    ok(11, "policy-header.json has required fields: header (starts with #) and version")
except Exception:
    fail_t(11, "policy-header.json missing required fields or header does not start with #")

# t12
expected_header = ph.get("header", "") if isinstance(ph, dict) else ""
result = subprocess.run([sys.executable, GENERATE_SCRIPT], capture_output=True, text=True)
actual_first = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
if expected_header == actual_first:
    ok(12, "generate-claude-md.py first line matches policy-header.json header field")
else:
    fail_t(12, "generate-claude-md.py first line does not match policy-header.json header field")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
