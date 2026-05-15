#!/usr/bin/env python3
"""Hook enforcement tests for scope-guard."""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")
SETTINGS_JSON = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/settings.json")
FEATURE_JSON = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/feature.json")

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


def run_scope_guard(input_json):
    result = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=input_json, capture_output=True, text=True,
    )
    return result.returncode


print("test-hook-enforcement.py")
print()
print("=== GUARANTEE 1: scope-guard restricts writes to active feature directory ===")

sg_src = read(SCOPE_GUARD)

# t1
if "find-feature.py" in sg_src and not re.search(r"registry\.json", sg_src):
    ok(1, "scope-guard.py uses find-feature.py for feature path lookup (no registry.json)")
else:
    fail_t(1, "scope-guard.py does NOT use find-feature.py for feature path lookup (or still references registry.json)")

# t2: setup marker pointing to rabbit-cage, then test deny on contract write
MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")
marker_existed = os.path.isfile(MARKER)
marker_backup = read(MARKER) if marker_existed else ""

with open(MARKER, "w") as f:
    f.write("rabbit-cage")

t2_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/contract/foo.txt"}}'
t2_exit = run_scope_guard(t2_input)

if t2_exit == 2:
    ok(2, "scope-guard exits 2 (deny) for Write to .claude/features/contract/ when scope is rabbit-cage")
else:
    fail_t(2, f"scope-guard exited {t2_exit} (expected 2/deny) for Write outside active feature dir — directory restriction not implemented")

# Restore marker
if marker_existed:
    with open(MARKER, "w") as f:
        f.write(marker_backup)
else:
    if os.path.isfile(MARKER):
        os.remove(MARKER)

print()
print("=== GUARANTEE 2: scope-guard blocks writes to a feature in test-green state ===")

# t3
if "tdd_state" in sg_src:
    ok(3, "scope-guard.py references tdd_state — has test-green enforcement logic")
else:
    fail_t(3, "scope-guard.py does NOT reference tdd_state — missing test-green block logic")

# t4: test-red allows, test-green denies
marker_existed = os.path.isfile(MARKER)
marker_backup = read(MARKER) if marker_existed else ""

with open(MARKER, "w") as f:
    f.write("rabbit-cage")

feature_json_backup = read(FEATURE_JSON)

# Part A: test-red
d = json.loads(feature_json_backup)
d["tdd_state"] = "test-red"
with open(FEATURE_JSON, "w") as f:
    json.dump(d, f, indent=2)

t4a_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t4a_exit = run_scope_guard(t4a_input)

# Part B: test-green
d["tdd_state"] = "test-green"
with open(FEATURE_JSON, "w") as f:
    json.dump(d, f, indent=2)

t4b_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t4b_exit = run_scope_guard(t4b_input)

# Restore feature.json
with open(FEATURE_JSON, "w") as f:
    f.write(feature_json_backup)

# Restore marker
if marker_existed:
    with open(MARKER, "w") as f:
        f.write(marker_backup)
else:
    if os.path.isfile(MARKER):
        os.remove(MARKER)

if t4a_exit == 0 and t4b_exit == 2:
    ok(4, "scope-guard exits 0 for test-red and exits 2 for test-green on same Write target")
elif t4a_exit != 0:
    fail_t(4, f"scope-guard exited {t4a_exit} (expected 0) when tdd_state=test-red — allow path broken")
else:
    fail_t(4, f"scope-guard exited {t4b_exit} (expected 2) when tdd_state=test-green — test-green block not implemented")

print()
print("=== CLEANUP: inert Agent hook artifacts removed ===")

settings_src = read(SETTINGS_JSON)
# t5
if '"Write|Edit|Bash|Agent"' not in settings_src:
    ok(5, "PreToolUse matcher does not contain Agent (inert hook cleaned up)")
else:
    fail_t(5, "PreToolUse matcher still contains Agent — inert hook not cleaned up")

# t6
policy_hook = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/rbt-policy-check.sh")
if not os.path.isfile(policy_hook):
    ok(6, "rbt-policy-check.sh does not exist (inert hook removed)")
else:
    fail_t(6, "rbt-policy-check.sh still exists — inert hook not cleaned up")

print()
print("=== METADATA EXCEPTION: rabbit-feature-touch excludes bug/backlog filing ===")

skill_md = os.path.join(REPO_ROOT, ".claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md")
skill_src = read(skill_md)
if re.search(r"bug.filing|backlog.filing|metadata.only|not for.*bug|not for.*backlog", skill_src, re.IGNORECASE):
    ok(7, "rabbit-feature-touch SKILL.md excludes metadata-only operations (bug/backlog filing)")
else:
    fail_t(7, "rabbit-feature-touch SKILL.md does not exclude metadata-only operations — bug/backlog filing incorrectly triggers TDD")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
