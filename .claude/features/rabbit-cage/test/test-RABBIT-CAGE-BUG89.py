#!/usr/bin/env python3
"""Tests scope-guard.py BUG-8 (spec.md path-pattern allowlist) and BUG-9
(strip-before-split for ;|& inside quoted args).

BUG-8 — Inv 64 (extended): scope-guard.py must permit writes to
`.claude/features/<feature>/docs/spec/spec.md` for any single path segment
`<feature>` (matched as `[^/]+`) regardless of scope-marker state. This
unblocks rabbit-feature-touch Step 3 spec-authoring which runs from the
main session before any per-feature scope marker is set.

BUG-9 — Inv 69 (extended): the quote-stripping pass in
`extract_bash_targets()` must run on the FULL command string BEFORE
splitting on `;|&` segment delimiters. Otherwise ;|& inside a quoted
argument value (e.g., a `--description "text with ; and <feature>)."`)
will produce spurious segments with unbalanced quotes, leading to
false-positive write target extraction such as `).`.
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


print("test-RABBIT-CAGE-BUG89.py")
print()
print("=== Setup: clear scope markers and override ===")

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
    print("=== BUG-8 (a) Write to feature spec.md ALLOW without scope marker ===")

    # t1: write to .claude/features/rabbit-cage/docs/spec/spec.md
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/features/rabbit-cage/docs/spec/spec.md","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 0:
        ok("Write to .claude/features/rabbit-cage/docs/spec/spec.md exits 0 (ALLOW) without scope marker")
    else:
        fail_t(
            f"Write to feature spec.md exits {exit_code} (expected 0/ALLOW); stderr: {stderr.strip()}"
        )

    # t2: pattern is generic — any single-segment <feature>
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/features/some-other-feature/docs/spec/spec.md","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 0:
        ok("Write to .claude/features/some-other-feature/docs/spec/spec.md exits 0 (ALLOW)")
    else:
        fail_t(
            f"Write to other feature spec.md exits {exit_code} (expected 0/ALLOW); stderr: {stderr.strip()}"
        )

    print()
    print("=== BUG-8 (b) Negative regression: pattern is narrow to spec.md only ===")

    # t3: scripts/ under same feature must still DENY
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/features/rabbit-cage/scripts/foo.py","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 2:
        ok("Write to feature scripts/foo.py DENIED (exit 2) — pattern correctly narrow")
    else:
        fail_t(
            f"Write to feature scripts/foo.py exit {exit_code} (expected 2/DENY) — pattern too broad"
        )

    # t4: other docs files under feature must still DENY (only spec.md is allowed)
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/features/rabbit-cage/docs/other.md","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 2:
        ok("Write to feature docs/other.md DENIED (exit 2) — narrowly scoped to spec.md")
    else:
        fail_t(
            f"Write to docs/other.md exit {exit_code} (expected 2/DENY) — pattern matches non-spec.md"
        )

    # t5: a multi-segment <feature> portion (with extra '/') must NOT be allowed
    write_json = (
        '{"tool_name":"Write","tool_input":{"file_path":"'
        + REPO_ROOT + '/.claude/features/foo/bar/docs/spec/spec.md","content":"x"}}'
    )
    exit_code, stderr = run_scope_guard(write_json)
    if exit_code == 2:
        ok("Write to multi-segment .../foo/bar/docs/spec/spec.md DENIED — [^/]+ enforced")
    else:
        fail_t(
            f"Multi-segment feature path exit {exit_code} (expected 2/DENY) — [^/]+ not enforced"
        )

    print()
    print("=== BUG-9 (a) Quoted ;|& must not produce spurious segments ===")

    # t6: --description with ; and <feature>) inside quotes — should not extract ').'
    # This simulates rabbit-feature-touch invoking a python3 script with a
    # --description argument containing the literal text "<feature>)." that
    # currently triggers a spurious DENY on ').'
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":'
        '"python3 script.py --description \\"text with ; and <feature>).\\""}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 0:
        ok("Bash with --description containing ; and <feature>). exits 0 (no false-positive)")
    else:
        fail_t(
            f"Bash --description \"...;...<feature>).\" exits {exit_code} "
            f"(expected 0/ALLOW); stderr: {stderr.strip()}"
        )

    # t7: similar but with | inside quotes
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":'
        '"python3 script.py --description \\"a | b > /tmp/x\\""}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 0:
        ok("Bash --description containing | and > inside quotes exits 0 (no false-positive)")
    else:
        fail_t(
            f"Bash --description with | and > inside quotes exits {exit_code} "
            f"(expected 0/ALLOW); stderr: {stderr.strip()}"
        )

    # t8: & inside quotes
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":'
        '"python3 script.py --description \\"foo & bar > '
        + REPO_ROOT + '/.claude/features/rabbit-cage/scripts/x.py\\""}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 0:
        ok("Bash with & and > inside quotes (target inside feature) exits 0 — quote stripped before split")
    else:
        fail_t(
            f"Bash with & inside quotes exits {exit_code} (expected 0/ALLOW); stderr: {stderr.strip()}"
        )

    print()
    print("=== BUG-9 (b) Regression: real unquoted redirects still DENY ===")

    # t9: real unquoted redirect to a feature path must still DENY (no scope marker)
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":"echo x > '
        + REPO_ROOT + '/.claude/features/rabbit-cage/scripts/evil.py"}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 2:
        ok("Real unquoted redirect to feature scripts/ still DENIED (no regression)")
    else:
        fail_t(
            f"Real unquoted redirect exit {exit_code} (expected 2/DENY) — REGRESSION"
        )

    # t10: real unquoted redirect chain separated by ; must still detect target
    bash_json = (
        '{"tool_name":"Bash","tool_input":{"command":"true ; echo x > '
        + REPO_ROOT + '/.claude/features/rabbit-cage/scripts/evil2.py"}}'
    )
    exit_code, stderr = run_scope_guard(bash_json)
    if exit_code == 2:
        ok("Real ; segment with redirect to feature scripts/ still DENIED — segment split intact for unquoted")
    else:
        fail_t(
            f"Real ; chain with redirect exit {exit_code} (expected 2/DENY) — REGRESSION"
        )

finally:
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
