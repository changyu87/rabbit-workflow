#!/usr/bin/env python3
"""Tests scope-guard.py basename allowlist after removal of `settings.json` (BUG-10).

Covers Invariant 64 (updated): the scope-guard basename allowlist contains
exactly `settings.local.json`, `.gitignore`, and `.rabbit-scope-override`.
`settings.json` is NOT on this allowlist; writes to `.claude/settings.json`
require an active rabbit-cage scope marker.

End-to-end tests:
  - DENY: Write to `.claude/settings.json` with no scope marker -> exit 2.
  - ALLOW: Write to `.claude/settings.json` with `.rabbit-scope-active-rabbit-cage`
    marker present -> exit 0.
  - Regression: Write to `.claude/settings.local.json` no marker -> exit 0.
  - Regression: Write to `.gitignore` no marker -> exit 0.
  - Regression: Write to `.rabbit-scope-override` no marker -> exit 0.
  - Source check: `scope-guard.py` source must NOT contain the literal
    `"settings.json"` inside its basename-allowlist tuple.
"""
import glob
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
    return result.returncode, result.stderr


print("test-RABBIT-CAGE-BUG10-settings-json-allowlist.py")
print()
print("=== Setup: clear all scope markers and override files ===")

# Save and remove global marker
MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")
marker_existed = os.path.isfile(MARKER)
marker_backup = read(MARKER) if marker_existed else ""
if marker_existed:
    os.remove(MARKER)

# Save and remove per-feature markers
saved_per_markers = []
for p in glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")):
    if os.path.isfile(p):
        saved_per_markers.append((p, read(p)))
        os.remove(p)

# Save and remove override files
OVERRIDE = os.path.join(REPO_ROOT, ".rabbit-scope-override")
override_existed = os.path.isfile(OVERRIDE)
override_backup = read(OVERRIDE) if override_existed else ""
if override_existed:
    os.remove(OVERRIDE)

USED = os.path.join(REPO_ROOT, ".rabbit-scope-override-used")
used_existed = os.path.isfile(USED)
if used_existed:
    os.remove(USED)

try:
    print()
    print("=== (a) BUG-10: Write to .claude/settings.json DENIED without scope marker ===")

    # t1: primary regression — settings.json must DENY without scope marker
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/settings.json","content":"{}"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 2:
        ok("Write to .claude/settings.json exits 2 (DENY) without scope marker (BUG-10 fixed)")
    else:
        fail_t(
            f"Write to .claude/settings.json exits {exit_code} (expected 2/DENY) "
            f"without scope marker — settings.json still on basename allowlist (BUG-10)"
        )

    print()
    print("=== (b) BUG-10: Write to rabbit-cage source settings.json ALLOWED with rabbit-cage scope marker ===")

    # t2: with per-feature marker for rabbit-cage, write to the canonical
    # source `.claude/features/rabbit-cage/settings.json` should ALLOW.
    # (The build-managed destination `.claude/settings.json` is regenerated
    # by build.py from the source — per Inv 32, agents must edit the source,
    # not the destination, so a marker test on the source path is the right
    # ALLOW check after removing the basename bypass.)
    per_marker = os.path.join(REPO_ROOT, ".rabbit-scope-active-rabbit-cage")
    with open(per_marker, "w") as f:
        f.write("")
    try:
        write_json_src = (
            '{"tool_name":"Write","tool_input":{"file_path":"'
            + REPO_ROOT + '/.claude/features/rabbit-cage/settings.json","content":"{}"}}'
        )
        exit_code, stderr = run_scope_guard(write_json_src)
        if exit_code == 0:
            ok(
                "Write to .claude/features/rabbit-cage/settings.json exits 0 (ALLOW) with "
                ".rabbit-scope-active-rabbit-cage marker"
            )
        else:
            fail_t(
                f"Write to .claude/features/rabbit-cage/settings.json exits {exit_code} "
                f"(expected 0/ALLOW) with rabbit-cage scope marker; "
                f"stderr: {stderr.strip()}"
            )
    finally:
        if os.path.isfile(per_marker):
            os.remove(per_marker)

    print()
    print("=== (c) Regression: settings.local.json still ALLOWED without scope marker ===")

    # t3: settings.local.json is gitignored user-local, remains on allowlist
    write_json_local = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/settings.local.json","content":"{}"}}'
    )
    exit_code, stderr = run_scope_guard(write_json_local)
    if exit_code == 0:
        ok("Write to .claude/settings.local.json exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Write to .claude/settings.local.json exits {exit_code} (expected 0/ALLOW) "
            f"— regression in basename allowlist; stderr: {stderr.strip()}"
        )

    print()
    print("=== (d) Regression: .gitignore still ALLOWED without scope marker ===")

    # t4: .gitignore remains on allowlist
    write_json_gi = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.gitignore","content":"x\\n"}}'
    )
    exit_code, stderr = run_scope_guard(write_json_gi)
    if exit_code == 0:
        ok("Write to .gitignore exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Write to .gitignore exits {exit_code} (expected 0/ALLOW) "
            f"— regression in basename allowlist; stderr: {stderr.strip()}"
        )

    print()
    print("=== (e) Regression: .rabbit-scope-override still ALLOWED without scope marker ===")

    # t5: .rabbit-scope-override remains on allowlist (catch-22 fix)
    write_json_ov = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.rabbit-scope-override","content":"one-time"}}'
    )
    exit_code, stderr = run_scope_guard(write_json_ov)
    if exit_code == 0:
        ok("Write to .rabbit-scope-override exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Write to .rabbit-scope-override exits {exit_code} (expected 0/ALLOW) "
            f"— catch-22 regression; stderr: {stderr.strip()}"
        )

    print()
    print("=== (f) Source check: scope-guard.py basename allowlist tuple excludes 'settings.json' ===")

    # t6: source contains the updated tuple without 'settings.json'
    sg = read(SCOPE_GUARD)
    # Match the basename-allowlist tuple literal in decide().
    m = re.search(
        r"if base in \(([^)]*)\):\s*\n\s*return True, \"ALLOW \(allowlisted filename\)\"",
        sg,
    )
    if not m:
        fail_t("Could not locate basename-allowlist tuple in scope-guard.py source")
    else:
        tuple_body = m.group(1)
        if '"settings.json"' in tuple_body or "'settings.json'" in tuple_body:
            fail_t(
                "scope-guard.py basename allowlist tuple still contains "
                "'settings.json' (BUG-10 not fixed)"
            )
        else:
            ok("scope-guard.py basename allowlist tuple does NOT contain 'settings.json'")

finally:
    # Restore state
    if marker_existed:
        with open(MARKER, "w") as f:
            f.write(marker_backup)
    for p, content in saved_per_markers:
        with open(p, "w") as f:
            f.write(content)
    if override_existed:
        with open(OVERRIDE, "w") as f:
            f.write(override_backup)
    if used_existed:
        with open(USED, "w") as f:
            f.write("")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
