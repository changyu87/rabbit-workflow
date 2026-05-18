#!/usr/bin/env python3
"""Hook enforcement tests for scope-guard.

Inv 64: this test MUST NOT mutate live source files. Marker and feature.json
mutations happen in an isolated temp git repo with copies of scope-guard.py
and find-feature.py. Live repo files are read-only here.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD_SRC = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")
SETTINGS_JSON = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/settings.json")
FIND_FEATURE_SRC = os.path.join(REPO_ROOT, ".claude/features/contract/scripts/find-feature.py")

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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def make_sandbox():
    """Create isolated git repo with scope-guard, find-feature, and a fake
    rabbit-cage feature directory + feature.json. Returns repo path + scope-guard path."""
    d = tempfile.mkdtemp(prefix="test-hook-enforcement-")
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "t"], check=True)
    sg_dir = os.path.join(d, ".claude/features/rabbit-cage/hooks")
    cage_dir = os.path.join(d, ".claude/features/rabbit-cage")
    contract_dir = os.path.join(d, ".claude/features/contract/scripts")
    contract_feat_dir = os.path.join(d, ".claude/features/contract")
    os.makedirs(sg_dir, exist_ok=True)
    os.makedirs(contract_dir, exist_ok=True)
    shutil.copy(SCOPE_GUARD_SRC, os.path.join(sg_dir, "scope-guard.py"))
    if os.path.isfile(FIND_FEATURE_SRC):
        shutil.copy(FIND_FEATURE_SRC, os.path.join(contract_dir, "find-feature.py"))
    # Place a feature.json in rabbit-cage directory (test-red default)
    with open(os.path.join(cage_dir, "feature.json"), "w") as f:
        json.dump({"name": "rabbit-cage", "tdd_state": "test-red"}, f, indent=2)
    # Also a contract feature so the "outside scope" target resolves
    with open(os.path.join(contract_feat_dir, "feature.json"), "w") as f:
        json.dump({"name": "contract", "tdd_state": "test-red"}, f, indent=2)
    with open(os.path.join(d, "placeholder"), "w") as f:
        f.write("x\n")
    subprocess.run(["git", "-C", d, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return d, os.path.join(sg_dir, "scope-guard.py")


def run_scope_guard(sg_path, sandbox, input_json):
    result = subprocess.run(
        [sys.executable, sg_path],
        input=input_json, capture_output=True, text=True,
        cwd=sandbox,
    )
    return result.returncode


print("test-hook-enforcement.py")
print()

# Snapshot live source files to enforce Inv 64 at the end of this test.
LIVE_TARGETS = {
    "settings.json": SETTINGS_JSON,
    "rabbit-cage feature.json": os.path.join(
        REPO_ROOT, ".claude/features/rabbit-cage/feature.json"
    ),
}
PRE_SNAPSHOT = {k: sha256_file(p) for k, p in LIVE_TARGETS.items() if os.path.isfile(p)}

print("=== GUARANTEE 1: scope-guard restricts writes to active feature directory ===")

sg_src = read(SCOPE_GUARD_SRC)

# t1
if "find-feature.py" in sg_src and not re.search(r"registry\.json", sg_src):
    ok(1, "scope-guard.py uses find-feature.py for feature path lookup (no registry.json)")
else:
    fail_t(1, "scope-guard.py does NOT use find-feature.py for feature path lookup (or still references registry.json)")

sandboxes = []
try:
    # t2: setup marker pointing to rabbit-cage in sandbox, then test deny on contract write
    sandbox, sg_path = make_sandbox()
    sandboxes.append(sandbox)
    MARKER = os.path.join(sandbox, ".rabbit-scope-active")
    with open(MARKER, "w") as f:
        f.write("rabbit-cage")
    target = os.path.join(sandbox, ".claude/features/contract/foo.txt")
    t2_input = json.dumps({"tool_name": "Write", "tool_input": {"file_path": target}})
    t2_exit = run_scope_guard(sg_path, sandbox, t2_input)
    if t2_exit == 2:
        ok(2, "scope-guard exits 2 (deny) for Write to .claude/features/contract/ when scope is rabbit-cage")
    else:
        fail_t(2, f"scope-guard exited {t2_exit} (expected 2/deny) for Write outside active feature dir")

    print()
    print("=== GUARANTEE 2: scope-guard blocks writes to a feature in test-green state ===")

    # t3
    if "tdd_state" in sg_src:
        ok(3, "scope-guard.py references tdd_state — has test-green enforcement logic")
    else:
        fail_t(3, "scope-guard.py does NOT reference tdd_state — missing test-green block logic")

    # t4: test-red allows, test-green denies — in isolated sandbox
    sandbox, sg_path = make_sandbox()
    sandboxes.append(sandbox)
    MARKER = os.path.join(sandbox, ".rabbit-scope-active")
    with open(MARKER, "w") as f:
        f.write("rabbit-cage")
    FEATURE_JSON = os.path.join(sandbox, ".claude/features/rabbit-cage/feature.json")

    # Part A: test-red
    with open(FEATURE_JSON, "w") as f:
        json.dump({"name": "rabbit-cage", "tdd_state": "test-red"}, f, indent=2)
    target = os.path.join(sandbox, ".claude/features/rabbit-cage/somefile.txt")
    t4a_input = json.dumps({"tool_name": "Write", "tool_input": {"file_path": target}})
    t4a_exit = run_scope_guard(sg_path, sandbox, t4a_input)

    # Part B: test-green
    with open(FEATURE_JSON, "w") as f:
        json.dump({"name": "rabbit-cage", "tdd_state": "test-green"}, f, indent=2)
    t4b_input = json.dumps({"tool_name": "Write", "tool_input": {"file_path": target}})
    t4b_exit = run_scope_guard(sg_path, sandbox, t4b_input)

    if t4a_exit == 0 and t4b_exit == 2:
        ok(4, "scope-guard exits 0 for test-red and exits 2 for test-green on same Write target")
    elif t4a_exit != 0:
        fail_t(4, f"scope-guard exited {t4a_exit} (expected 0) when tdd_state=test-red")
    else:
        fail_t(4, f"scope-guard exited {t4b_exit} (expected 2) when tdd_state=test-green")
finally:
    for s in sandboxes:
        shutil.rmtree(s, ignore_errors=True)

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

skill_md = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/skills/rabbit-feature-touch/SKILL.md")
skill_src = read(skill_md)
if re.search(r"bug.filing|backlog.filing|metadata.only|not for.*bug|not for.*backlog", skill_src, re.IGNORECASE):
    ok(7, "rabbit-feature-touch SKILL.md excludes metadata-only operations (bug/backlog filing)")
else:
    fail_t(7, "rabbit-feature-touch SKILL.md does not exclude metadata-only operations — bug/backlog filing incorrectly triggers TDD")

print()
print("=== Inv 64: live source files were not mutated ===")
post = {k: sha256_file(p) for k, p in LIVE_TARGETS.items() if os.path.isfile(p)}
drifted = [k for k in PRE_SNAPSHOT if PRE_SNAPSHOT[k] != post.get(k)]
if not drifted:
    ok(8, "live source files byte-identical after test (Inv 64)")
else:
    fail_t(8, f"live source files mutated by test (Inv 64 violation): {drifted}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
