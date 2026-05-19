#!/usr/bin/env python3
"""Tests scope-guard.py path-prefix allowlist for .rabbit/, .claude/bugs/, .claude/backlogs/.

Covers Invariant 20 path-prefix allowlist:
- Writes anywhere under .claude/bugs/, .claude/backlogs/, or .rabbit/ are
  always permitted regardless of scope-marker state.
- The .rabbit/ prefix is required so rabbit-feature-touch dispatchers can
  write .rabbit/impl-suggestion-<feature>.json and .rabbit/tdd-report-<feature>.json
  during normal feature work without needing a session override.
"""
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
    return result.returncode, result.stderr


print("test-scope-guard-rabbit-allowlist.py")
print()
print("=== Setup: clear scope markers and override ===")

# Save and remove all scope markers + override files
MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")
marker_existed = os.path.isfile(MARKER)
marker_backup = read(MARKER) if marker_existed else ""
if marker_existed:
    os.remove(MARKER)

saved_per_markers = []
for p in glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")):
    if os.path.isfile(p):
        saved_per_markers.append((p, read(p)))
        os.remove(p)

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
    print("=== (a) Write to .rabbit/ paths is ALLOW without scope marker ===")

    # t1: impl-suggestion file
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.rabbit/impl-suggestion-rabbit-cage.json","content":"{}"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 0:
        ok("Write to .rabbit/impl-suggestion-rabbit-cage.json exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Write to .rabbit/impl-suggestion-rabbit-cage.json exits {exit_code} "
            f"(expected 0/ALLOW); stderr: {stderr.strip()}"
        )

    # t2: tdd-report file
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.rabbit/tdd-report-rabbit-cage.json","content":"{}"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 0:
        ok("Write to .rabbit/tdd-report-rabbit-cage.json exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Write to .rabbit/tdd-report-rabbit-cage.json exits {exit_code} "
            f"(expected 0/ALLOW); stderr: {stderr.strip()}"
        )

    # t3: arbitrary subdir under .rabbit/
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.rabbit/subdir/file.json","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 0:
        ok("Write to .rabbit/subdir/file.json exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Write to .rabbit/subdir/file.json exits {exit_code} (expected 0/ALLOW); "
            f"stderr: {stderr.strip()}"
        )

    # t4: Bash redirect to .rabbit/
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":"echo x > '
        + REPO_ROOT + '/.rabbit/foo.json"}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 0:
        ok("Bash redirect to .rabbit/foo.json exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Bash redirect to .rabbit/foo.json exits {exit_code} (expected 0/ALLOW); "
            f"stderr: {stderr.strip()}"
        )

    print()
    print("=== (b) Regression: existing .claude/bugs/ and .claude/backlogs/ still ALLOW ===")

    # t5: .claude/bugs/
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/bugs/foo.md","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 0:
        ok(".claude/bugs/ write still exits 0 (ALLOW) — regression")
    else:
        fail_t(
            f".claude/bugs/ write exits {exit_code} (expected 0/ALLOW) — REGRESSION; "
            f"stderr: {stderr.strip()}"
        )

    # t6: .claude/backlogs/
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/backlogs/foo.md","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 0:
        ok(".claude/backlogs/ write still exits 0 (ALLOW) — regression")
    else:
        fail_t(
            f".claude/backlogs/ write exits {exit_code} (expected 0/ALLOW) — REGRESSION; "
            f"stderr: {stderr.strip()}"
        )

    print()
    print("=== (c) Negative: write outside allowlist still DENY without scope marker ===")

    # t7: a write to a feature dir outside allowlist must still DENY
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/features/rabbit-cage/some-new-file.txt","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code != 0:
        ok("Write to .claude/features/rabbit-cage/some-new-file.txt DENIED as expected (no scope marker)")
    else:
        fail_t(
            "Write to .claude/features/rabbit-cage/some-new-file.txt unexpectedly ALLOWED "
            "without scope marker — default-deny broken"
        )

    print()
    print("=== (d) Spec/source check: .rabbit/ appears in scope-guard.py ===")

    sg = read(SCOPE_GUARD)
    if "/.rabbit/" in sg or ".rabbit" in sg:
        ok("scope-guard.py source contains '.rabbit' prefix")
    else:
        fail_t("scope-guard.py source does NOT contain '.rabbit' prefix")

    print()
    print("=== (e) BUG-87: exact directory path matches path-prefix allowlist ===")

    # t8: Bash `mkdir .rabbit` (exact directory match, no trailing slash) → ALLOW
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":"mkdir '
        + REPO_ROOT + '/.rabbit"}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 0:
        ok("Bash 'mkdir .rabbit' exits 0 (ALLOW) — exact dir match (BUG-87)")
    else:
        fail_t(
            f"Bash 'mkdir .rabbit' exits {exit_code} (expected 0/ALLOW) — BUG-87; "
            f"stderr: {stderr.strip()}"
        )

    # t9: Bash `mkdir .rabbit/sub` (path inside .rabbit) → ALLOW (regression guard)
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":"mkdir '
        + REPO_ROOT + '/.rabbit/sub"}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 0:
        ok("Bash 'mkdir .rabbit/sub' exits 0 (ALLOW) — path-inside match")
    else:
        fail_t(
            f"Bash 'mkdir .rabbit/sub' exits {exit_code} (expected 0/ALLOW); "
            f"stderr: {stderr.strip()}"
        )

    # t10: Bash write to .rabbit-other-sibling → DENY (sibling, not allowlisted)
    # Use `touch` so the target is unambiguous and matches a non-marker basename.
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":"touch '
        + REPO_ROOT + '/.rabbit-other-sibling"}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code != 0:
        ok("Bash 'touch .rabbit-other-sibling' DENIED — sibling not matched by allowlist")
    else:
        fail_t(
            "Bash 'touch .rabbit-other-sibling' unexpectedly ALLOWED — "
            "exact-match check must be strict equality, not prefix"
        )

finally:
    # Restore
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
