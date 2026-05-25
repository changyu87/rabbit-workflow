#!/usr/bin/env python3
"""Inv 3, 4, 5, 6 — CLI flag set, exit codes, boolean vocabulary,
--linked-items validation."""
from _helpers import run_dispatch, run_dispatch_raw, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


# Inv 3: success path → exit 0, stdout non-empty.
res = run_dispatch()
if res.returncode == 0 and res.stdout.strip():
    ok("inv3: success path returns 0 with non-empty stdout")
else:
    ko(f"inv3: baseline dispatch failed: rc={res.returncode}, stdout_len={len(res.stdout)}, stderr={res.stderr!r}")

# Inv 3 + Inv 4: missing --scope → exit 2.
res = run_dispatch_raw("--spec", "/tmp/whatever")
if res.returncode == 2:
    ok("inv4: missing --scope exits 2")
else:
    ko(f"inv4: expected 2 for missing --scope, got {res.returncode}")

# Inv 3 + Inv 4: missing --spec → exit 2.
res = run_dispatch_raw("--scope", "tdd-subagent")
if res.returncode == 2:
    ok("inv4: missing --spec exits 2")
else:
    ko(f"inv4: expected 2 for missing --spec, got {res.returncode}")

# Inv 3: unknown --scope feature → exit 2.
res = run_dispatch(scope="nonexistent-feature-xyz")
if res.returncode == 2:
    ok("inv3: unknown --scope exits 2")
else:
    ko(f"inv3: expected 2 for unknown scope, got {res.returncode}")

# Inv 3: --spec path does not exist → exit 2.
res = run_dispatch(spec="/tmp/this-file-does-not-exist-xyz")
if res.returncode == 2:
    ok("inv3: nonexistent --spec exits 2")
else:
    ko(f"inv3: expected 2 for missing spec file, got {res.returncode}")

# Inv 3: --linked-item without --item-type → exit 2.
res = run_dispatch("--linked-item", "/tmp/dummy")
if res.returncode == 2:
    ok("inv3: --linked-item without --item-type exits 2")
else:
    ko(f"inv3: expected 2 for unpaired --linked-item, got {res.returncode}")

# Inv 3: --item-type without --linked-item → exit 2.
res = run_dispatch("--item-type", "bug")
if res.returncode == 2:
    ok("inv3: --item-type without --linked-item exits 2")
else:
    ko(f"inv3: expected 2 for unpaired --item-type, got {res.returncode}")

# Inv 3 + Inv 4: --max-iterations 0 → exit 2.
res = run_dispatch("--max-iterations", "0")
if res.returncode == 2:
    ok("inv4: --max-iterations 0 exits 2")
else:
    ko(f"inv4: expected 2 for max-iterations 0, got {res.returncode}")

# Inv 4: --human-approval-gate flag retired (TDD-SUBAGENT-BACKLOG-19); argparse
# must reject it as an unrecognized argument. Cover both the prior 'true' and
# 'false' values to guarantee no residual codepath honours the flag.
res = run_dispatch("--human-approval-gate", "true")
if res.returncode == 2:
    ok("inv4: --human-approval-gate true rejected (flag retired)")
else:
    ko(f"inv4: expected 2 for retired --human-approval-gate true, got {res.returncode}")

res = run_dispatch("--human-approval-gate", "false")
if res.returncode == 2:
    ok("inv4: --human-approval-gate false rejected (flag retired)")
else:
    ko(f"inv4: expected 2 for retired --human-approval-gate false, got {res.returncode}")

# Inv 6: --linked-items malformed entry (wrong colon count) → exit 2.
res = run_dispatch("--linked-items", "rabbit-cage:bug")
if res.returncode == 2 and "two colons" in res.stderr:
    ok("inv6: malformed --linked-items (wrong colon count) exits 2 with diagnostic")
else:
    ko(f"inv6: expected 2 + diagnostic, got rc={res.returncode}, stderr={res.stderr!r}")

# Inv 6: --linked-items invalid type → exit 2.
res = run_dispatch("--linked-items", "rabbit-cage:hotfix:RABBIT-CAGE-BUG-1")
if res.returncode == 2 and "invalid type" in res.stderr:
    ok("inv6: invalid type in --linked-items exits 2 with diagnostic")
else:
    ko(f"inv6: expected 2 + diagnostic, got rc={res.returncode}, stderr={res.stderr!r}")

# Inv 6: --linked-items empty field → exit 2.
res = run_dispatch("--linked-items", ":bug:BUG-1")
if res.returncode == 2 and "empty field" in res.stderr:
    ok("inv6: empty field in --linked-items exits 2 with diagnostic")
else:
    ko(f"inv6: expected 2 + diagnostic, got rc={res.returncode}, stderr={res.stderr!r}")

# Inv 6: malformed --linked-items must not emit prompt to stdout.
res = run_dispatch("--linked-items", "broken")
if res.returncode == 2 and res.stdout == "":
    ok("inv6: malformed --linked-items emits no stdout before exit")
else:
    ko(f"inv6: expected empty stdout for malformed entry, got stdout_len={len(res.stdout)}")

report(passed, failed)
