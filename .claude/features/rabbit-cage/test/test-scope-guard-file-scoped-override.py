#!/usr/bin/env python3
"""E2E test for Invariant 41: file-scoped one-time scope-guard override.

Verifies the third content form of the `.rabbit-scope-override` marker —
`one-time:<repo-relative-path>` — implemented by `_consume_override()` in
`hooks/scope-guard.py`, exercised end-to-end through the real scope-guard
subprocess with a JSON Write payload on stdin:

  (a) marker content `one-time:<declared>` + Write to `<declared>` is
      ALLOWED (exit 0) and the override is CONSUMED (the override marker is
      deleted and `.rabbit-scope-override-used` is created).
  (b) marker content `one-time:<declared>` + Write to a DIFFERENT path is
      DENIED (exit 2) and the override marker is RETAINED (not consumed).
  (c) after the authorized write consumes the marker, a SECOND Write to
      `<declared>` is DENIED (exit 2).
  (d) regression — bare `session` allows a write and RETAINS the marker;
      bare `one-time` allows a write and CONSUMES the marker.

All scenarios run against a clean repo-root marker state (every
`.rabbit-scope-active*` and `.rabbit-scope-override*` marker is saved and
removed for the duration of the test, then restored) so the default-deny
path is the only thing standing between the override and the write.
"""
import glob
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py"
)
OVERRIDE = os.path.join(REPO_ROOT, ".rabbit-scope-override")
USED = os.path.join(REPO_ROOT, ".rabbit-scope-override-used")

# Two distinct in-repo targets that are NOT on any allowlist (paths inside a
# feature's scripts/ dir without a scope marker fall to default-deny).
DECLARED_REL = ".claude/features/rabbit-cage/scripts/__fs_override_declared__.txt"
OTHER_REL = ".claude/features/rabbit-cage/scripts/__fs_override_other__.txt"
DECLARED_ABS = os.path.join(REPO_ROOT, DECLARED_REL)
OTHER_ABS = os.path.join(REPO_ROOT, OTHER_REL)

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


def run_scope_guard(target):
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": "x"},
    }
    result = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return result.returncode, result.stderr


def temporarily_clear_markers():
    """Clear all scope markers/overrides in repo root; return restore fn."""
    saved = []
    paths = [
        os.path.join(REPO_ROOT, ".rabbit-scope-active"),
        OVERRIDE,
        USED,
    ]
    paths.extend(glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")))
    for p in paths:
        if os.path.isfile(p):
            with open(p) as f:
                saved.append((p, f.read()))
            os.remove(p)

    def restore():
        # Remove anything the test created, then restore originals.
        for p in (OVERRIDE, USED):
            if os.path.isfile(p):
                os.remove(p)
        for p, content in saved:
            with open(p, "w") as f:
                f.write(content)
    return restore


def _clear_override_state():
    for p in (OVERRIDE, USED):
        if os.path.isfile(p):
            os.remove(p)


print("test-scope-guard-file-scoped-override.py")
print()
print("=== Invariant 41: file-scoped one-time override ===")

restore = temporarily_clear_markers()
try:
    # ---- (a) declared-path write is ALLOWED and CONSUMES the marker ----
    _clear_override_state()
    with open(OVERRIDE, "w") as f:
        f.write("one-time:" + DECLARED_REL)
    rc, stderr = run_scope_guard(DECLARED_ABS)
    if rc == 0:
        ok("file-scoped override ALLOWS write to declared path (exit 0)")
    else:
        fail_t(f"declared-path write denied (exit {rc}); stderr={stderr!r}")
    if not os.path.isfile(OVERRIDE):
        ok("file-scoped override marker is CONSUMED (deleted) after declared write")
    else:
        fail_t("override marker still present after declared-path write (not consumed)")
    if os.path.isfile(USED):
        ok(".rabbit-scope-override-used created on consume (Stop-hook alert path)")
    else:
        fail_t(".rabbit-scope-override-used NOT created on file-scoped consume")

    # ---- (b) other-path write is DENIED and RETAINS the marker ----
    _clear_override_state()
    with open(OVERRIDE, "w") as f:
        f.write("one-time:" + DECLARED_REL)
    rc, stderr = run_scope_guard(OTHER_ABS)
    if rc == 2:
        ok("file-scoped override DENIES write to a different path (exit 2)")
    else:
        fail_t(f"other-path write not denied (exit {rc}); stderr={stderr!r}")
    if os.path.isfile(OVERRIDE):
        ok("override marker RETAINED after denied other-path write (not widened)")
    else:
        fail_t("override marker consumed by a non-matching path (must be retained)")

    # ---- (c) after consume, a second declared write is DENIED ----
    _clear_override_state()
    with open(OVERRIDE, "w") as f:
        f.write("one-time:" + DECLARED_REL)
    rc1, _ = run_scope_guard(DECLARED_ABS)        # consumes
    rc2, stderr2 = run_scope_guard(DECLARED_ABS)  # marker gone now
    if rc1 == 0 and rc2 == 2:
        ok("second declared write after consume is DENIED (single-use)")
    else:
        fail_t(
            f"single-use not enforced: first={rc1} (want 0), "
            f"second={rc2} (want 2); stderr={stderr2!r}"
        )

    # ---- (d) regression: bare session ALLOWS + RETAINS ----
    _clear_override_state()
    with open(OVERRIDE, "w") as f:
        f.write("session")
    rc, stderr = run_scope_guard(DECLARED_ABS)
    if rc == 0:
        ok("regression: bare 'session' ALLOWS the write (exit 0)")
    else:
        fail_t(f"bare 'session' denied (exit {rc}); stderr={stderr!r}")
    if os.path.isfile(OVERRIDE):
        ok("regression: bare 'session' RETAINS the marker")
    else:
        fail_t("bare 'session' consumed the marker (must be retained)")

    # ---- (d) regression: bare one-time ALLOWS any path + CONSUMES ----
    _clear_override_state()
    with open(OVERRIDE, "w") as f:
        f.write("one-time")
    rc, stderr = run_scope_guard(OTHER_ABS)
    if rc == 0:
        ok("regression: bare 'one-time' ALLOWS a write to any path (exit 0)")
    else:
        fail_t(f"bare 'one-time' denied (exit {rc}); stderr={stderr!r}")
    if not os.path.isfile(OVERRIDE):
        ok("regression: bare 'one-time' CONSUMES the marker")
    else:
        fail_t("bare 'one-time' did not consume the marker")
finally:
    restore()

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
