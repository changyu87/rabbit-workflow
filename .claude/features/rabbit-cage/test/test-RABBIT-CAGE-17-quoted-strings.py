#!/usr/bin/env python3
"""Tests extract_bash_targets() in scope-guard.py is quote-aware."""
import importlib.util
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")

failures = 0


def ok(n, msg):
    print(f"  PASS t_rc17_{n}: {msg}")


def fail_t(n, msg):
    global failures
    print(f"  FAIL t_rc17_{n}: {msg}")
    failures += 1


def load_sg():
    spec = importlib.util.spec_from_file_location("sg", SCOPE_GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def extract_targets(cmd):
    m = load_sg()
    return list(m.extract_bash_targets(cmd))


print("test-RABBIT-CAGE-17-quoted-strings.py")
print()
print("=== RABBIT-CAGE-17: extract_bash_targets strips quoted regions ===")

# t1
cmd1 = """python3 -c 'import json; print({"action": "x > /tmp/evil"})'"""
targets1 = extract_targets(cmd1)
if any("/tmp/evil" in t for t in targets1):
    fail_t(1, "false positive: '/tmp/evil' detected as write target inside single-quoted string")
else:
    ok(1, "redirect inside single-quoted string is NOT detected as write target")

# t2
cmd2 = 'echo "result sending to > /tmp/evil"'
targets2 = extract_targets(cmd2)
if any("/tmp/evil" in t for t in targets2):
    fail_t(2, "false positive: '/tmp/evil' detected as write target inside double-quoted string")
else:
    ok(2, "redirect inside double-quoted string is NOT detected as write target")

# t3
cmd3 = "cat file > /tmp/real_output"
targets3 = extract_targets(cmd3)
if any("/tmp/real_output" in t for t in targets3):
    ok(3, "real unquoted redirect IS detected as write target (no regression)")
else:
    fail_t(3, "regression: real unquoted redirect '/tmp/real_output' was NOT detected")

# t4
cmd4 = "cat <<EOF\nline with > in body\ngoes to /tmp/heredoc_target\nEOF"
targets4 = extract_targets(cmd4)
if any("/tmp/heredoc_target" in t for t in targets4):
    fail_t(4, "false positive: heredoc body content detected as write target")
else:
    ok(4, "heredoc body with '>' is NOT detected as write target")

print()
print(f"Results: {4 - failures} passed, {failures} failed")
if failures > 0:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
print("ALL TESTS PASSED")
sys.exit(0)
