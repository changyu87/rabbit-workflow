#!/usr/bin/env python3
"""BACKLOG-19 / Inv 89: sync-check.py first-run path is removed.

(a) When CLAUDE.md is absent on disk, sync-check.py exits 0 with empty
    stdout (no first-run JSON is emitted, and CLAUDE.md is NOT created by
    sync-check.py — bootstrap is install.py's job, not sync-check's).
(b) The source of sync-check.py contains no `Policy initialized` literal.
(c) The source of sync-check.py contains no `first-run` literal in message
    bodies.
"""
import os
import subprocess
import sys
import tempfile
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")

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


print("test-RABBIT-CAGE-BACKLOG-19-first-run-removed.py")
print()

# (a) e2e: sync-check.py on a temp repo with no CLAUDE.md → exit 0, empty stdout
tmproot = tempfile.mkdtemp(prefix="rabbit-cage-bl19-")
try:
    # Build a minimal repo skeleton WITHOUT CLAUDE.md.
    import json
    os.makedirs(os.path.join(tmproot, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(tmproot, ".claude/features/policy"), exist_ok=True)
    for fname, content in [
        ("philosophy.md", "# Philosophy\n"),
        ("spec-rules.md", "# Spec Rules\n"),
        ("coding-rules.md", "# Coding Rules\n"),
    ]:
        with open(os.path.join(tmproot, ".claude/features/policy", fname), "w") as f:
            f.write(content)
    with open(os.path.join(tmproot, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test"}, f)
    for fname in ("generate-claude-md.py", "generate-claude-md-header.py"):
        shutil.copy(
            os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts", fname),
            os.path.join(tmproot, ".claude/features/rabbit-cage/scripts", fname),
        )

    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run(
        [sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True,
    )

    if res.returncode == 0:
        ok("sync-check.py exits 0 when CLAUDE.md absent")
    else:
        fail_t(f"sync-check.py exited {res.returncode} when CLAUDE.md absent (expected 0)")

    if res.stdout.strip() == "":
        ok("sync-check.py emits empty stdout when CLAUDE.md absent (no first-run JSON)")
    else:
        fail_t(f"sync-check.py emitted non-empty stdout when CLAUDE.md absent: {res.stdout!r}")

    if not os.path.isfile(os.path.join(tmproot, "CLAUDE.md")):
        ok("sync-check.py did NOT create CLAUDE.md when absent (first-run path removed)")
    else:
        fail_t("sync-check.py created CLAUDE.md when absent — first-run path should be removed")
finally:
    shutil.rmtree(tmproot, ignore_errors=True)

# (b) source-check
with open(SYNC_CHECK) as f:
    src = f.read()

if "Policy initialized" not in src:
    ok("sync-check.py source contains no `Policy initialized` literal")
else:
    fail_t("sync-check.py source still contains `Policy initialized` literal")

# (c) `first-run` in source — be lenient to permit a single comment marker
# explaining the removal, but assert no `first-run` appears in any
# string/message body. Cheap check: count occurrences in source minus
# occurrences in comment lines.
def occurrences_in_code(src, needle):
    count = 0
    for line in src.splitlines():
        s = line.lstrip()
        if s.startswith("#"):
            continue
        count += line.count(needle)
    return count

n = occurrences_in_code(src, "first-run")
if n == 0:
    ok("sync-check.py source has no `first-run` literal in code")
else:
    fail_t(f"sync-check.py source still contains {n} `first-run` literals in code")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
