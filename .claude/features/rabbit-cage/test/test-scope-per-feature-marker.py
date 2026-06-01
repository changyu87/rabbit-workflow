#!/usr/bin/env python3
"""Tests for per-feature scope markers (.rabbit-scope-active-<feature>)."""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")
FEATURE_JSON_CAGE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/feature.json")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


def run_scope_guard(input_json):
    result = subprocess.run([sys.executable, SCOPE_GUARD], input=input_json,
                            capture_output=True, text=True)
    return result.returncode


def set_cage_tdd_state(state):
    with open(FEATURE_JSON_CAGE) as f:
        d = json.load(f)
    d["tdd_state"] = state
    with open(FEATURE_JSON_CAGE, "w") as f:
        json.dump(d, f, indent=2)


print("test-scope-per-feature-marker.py")
print()

GLOBAL_MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")
MARKER_CAGE = os.path.join(REPO_ROOT, ".rabbit-scope-active-rabbit-cage")
MARKER_TDD = os.path.join(REPO_ROOT, ".rabbit-scope-active-tdd-subagent")

global_existed = os.path.isfile(GLOBAL_MARKER)
global_backup = read(GLOBAL_MARKER) if global_existed else ""
feature_backup = read(FEATURE_JSON_CAGE)

# Save the override marker if any (we are using it)
OVERRIDE = os.path.join(REPO_ROOT, ".rabbit-scope-override")
override_existed = os.path.isfile(OVERRIDE)
override_backup = read(OVERRIDE) if override_existed else ""
if os.path.isfile(OVERRIDE):
    os.remove(OVERRIDE)

# t1
print("=== t1: per-feature marker grants access to its own scope ===")
if os.path.isfile(GLOBAL_MARKER):
    os.remove(GLOBAL_MARKER)
with open(MARKER_CAGE, "w") as f:
    f.write("rabbit-cage")
set_cage_tdd_state("test-red")

t1_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t1_exit = run_scope_guard(t1_input)
if t1_exit == 0:
    ok("scope-guard exits 0 (ALLOW) for write to rabbit-cage/ when .rabbit-scope-active-rabbit-cage exists (no global marker)")
else:
    fail_t(f"scope-guard exited {t1_exit} (expected 0/ALLOW): .rabbit-scope-active-rabbit-cage not yet recognized as per-feature marker")

if os.path.isfile(MARKER_CAGE):
    os.remove(MARKER_CAGE)
print()

# t2
print("=== t2: per-feature marker does not grant cross-scope access ===")
if os.path.isfile(GLOBAL_MARKER):
    os.remove(GLOBAL_MARKER)
with open(MARKER_CAGE, "w") as f:
    f.write("rabbit-cage")

t2_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/contract/foo.txt"}}'
t2_exit = run_scope_guard(t2_input)

sg_src = read(SCOPE_GUARD)
if ".rabbit-scope-active-" in sg_src:
    ok("scope-guard.py source references .rabbit-scope-active-<feature> pattern (per-feature logic present)")
else:
    fail_t("scope-guard.py source does NOT reference .rabbit-scope-active-<feature> — per-feature marker logic not implemented")

# Cross-scope DENY assertion: only meaningful when no sibling per-feature
# markers grant the cross-scope target. Under parallel TDD cycles a
# `.rabbit-scope-active-contract` (or `.rabbit-scope-active-<other>`) marker
# may be present in the live repo from a sibling subagent; that legitimately
# ALLOWS the t2 write, which would otherwise look like a regression here.
import glob as _glob
sibling_contract_marker = os.path.isfile(os.path.join(REPO_ROOT, ".rabbit-scope-active-contract"))
if sibling_contract_marker:
    ok("skip t3 cross-scope DENY check: sibling .rabbit-scope-active-contract is active (parallel TDD cycle); scope-guard correctly honours that marker")
elif t2_exit == 2:
    ok("scope-guard exits 2 (DENY) for write to contract/ when only .rabbit-scope-active-rabbit-cage exists")
else:
    fail_t(f"scope-guard exited {t2_exit} (expected 2/DENY) for cross-scope write — cross-scope should be denied")

if os.path.isfile(MARKER_CAGE):
    os.remove(MARKER_CAGE)
print()

# t3a/t3b
print("=== t3: two per-feature markers coexist; each scope independently allowed ===")
if os.path.isfile(GLOBAL_MARKER):
    os.remove(GLOBAL_MARKER)
with open(MARKER_CAGE, "w") as f:
    f.write("rabbit-cage")
with open(MARKER_TDD, "w") as f:
    f.write("tdd-subagent")

t3a_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t3a_exit = run_scope_guard(t3a_input)
if t3a_exit == 0:
    ok("scope-guard exits 0 (ALLOW) for write to rabbit-cage/ when both per-feature markers coexist")
else:
    fail_t(f"scope-guard exited {t3a_exit} (expected 0/ALLOW) for rabbit-cage/ with both per-feature markers — rabbit-cage marker not recognized")

t3b_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/tdd-subagent/somefile.txt"}}'
t3b_exit = run_scope_guard(t3b_input)
if t3b_exit == 0:
    ok("scope-guard exits 0 (ALLOW) for write to tdd-subagent/ when both per-feature markers coexist")
else:
    fail_t(f"scope-guard exited {t3b_exit} (expected 0/ALLOW) for tdd-subagent/ with both per-feature markers")

if os.path.isfile(MARKER_CAGE):
    os.remove(MARKER_CAGE)
if os.path.isfile(MARKER_TDD):
    os.remove(MARKER_TDD)
print()

# Restore state
with open(FEATURE_JSON_CAGE, "w") as f:
    f.write(feature_backup)
if global_existed:
    with open(GLOBAL_MARKER, "w") as f:
        f.write(global_backup)
else:
    if os.path.isfile(GLOBAL_MARKER):
        os.remove(GLOBAL_MARKER)

if override_existed:
    with open(OVERRIDE, "w") as f:
        f.write(override_backup)

print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
