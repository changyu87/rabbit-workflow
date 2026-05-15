#!/usr/bin/env python3
"""Tests scope-guard.py allowlist for .rabbit-scope-override."""
import glob
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


print("test-scope-guard-allowlist.py")
print()
print("=== (a) scope-guard.py source contains .rabbit-scope-override in allowlist ===")

# t1
sg = read(SCOPE_GUARD)
if ".rabbit-scope-override" in sg:
    ok("scope-guard.py allowlist contains .rabbit-scope-override")
else:
    fail_t("scope-guard.py does NOT contain .rabbit-scope-override in filename allowlist")

print()
print("=== (b) Write to .rabbit-scope-override is ALLOW without scope marker ===")

MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")
marker_existed = os.path.isfile(MARKER)
marker_backup = read(MARKER) if marker_existed else ""
if marker_existed:
    os.remove(MARKER)

# Remove per-feature markers
saved_per_markers = []
for p in glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")):
    if os.path.isfile(p):
        saved_per_markers.append((p, read(p)))
        os.remove(p)

# t2
write_json = '{"tool_name":"Write","tool_input":{"file_path":"' + REPO_ROOT + '/.rabbit-scope-override","content":"one-time"}}'
t2_exit = run_scope_guard(write_json)
if t2_exit == 0:
    ok("Write to .rabbit-scope-override exits 0 (ALLOW) without any scope marker active")
else:
    fail_t(f"Write to .rabbit-scope-override exits {t2_exit} (expected 0/ALLOW) without scope marker — catch-22 not fixed")

# t3
write_json_rel = '{"tool_name":"Write","tool_input":{"file_path":".rabbit-scope-override","content":"one-time"}}'
t3_exit = run_scope_guard(write_json_rel)
if t3_exit == 0:
    ok("Write to .rabbit-scope-override (relative path) exits 0 (ALLOW) without scope marker")
else:
    fail_t(f"Write to .rabbit-scope-override (relative path) exits {t3_exit} (expected 0/ALLOW)")

# Restore
if marker_existed:
    with open(MARKER, "w") as f:
        f.write(marker_backup)
for p, content in saved_per_markers:
    with open(p, "w") as f:
        f.write(content)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
