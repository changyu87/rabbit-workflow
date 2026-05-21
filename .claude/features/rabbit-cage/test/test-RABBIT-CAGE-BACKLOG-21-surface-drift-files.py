#!/usr/bin/env python3
"""BACKLOG-21 E2E test for sync-check.py surface-drift target naming.

Spec Inv 88 (v3.11.0) requires the surface-drift renderer to:
  1. Read build-contract.json and identify copy-file targets whose
     destination sha256 differs from their source sha256.
  2. Pass the comma-joined target NAMES to surface_drift(files=...).
  3. Emit no surface-drift line when sources and destinations all match.

This test stands up a temp repo with a curated build-contract.json plus
matching source/destination files in each scenario, then invokes the live
sync-check.py and asserts on the rendered systemMessage.
"""
import json
import os
import shutil
import subprocess
import sys

from test_helpers import REPO_ROOT, make_git_repo, run_sync

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


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def write_contract(tmproot, targets):
    contract = {
        "schema_version": "1.0.0",
        "owner": "rabbit-workflow team",
        "deprecation_criterion": "test fixture",
        "updated": "2026-05-19",
        "targets": targets,
    }
    path = os.path.join(tmproot, ".claude/features/contract/build-contract.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(contract, f)


def parse_msg(out):
    try:
        return json.loads(out.strip()).get("systemMessage", "")
    except Exception:
        return ""


print("test-RABBIT-CAGE-BACKLOG-21-surface-drift-files.py")
print("E2E: surface-drift renderer names the actually-drifted targets")
print()

tmproots = []
try:
    # ---- t1: single drifted target — name appears in 'rebuilt:' ----
    print("=== t1: single drifted copy-file target — its name is named ===")
    root = make_git_repo()
    tmproots.append(root)

    src = os.path.join(root, "src/hooks/sync-check.py")
    dst = os.path.join(root, "dst/hooks/sync-check.py")
    write_file(src, "# real source content\n")
    write_file(dst, "# stale destination content\n")

    write_contract(root, [{
        "name": "hooks/sync-check.py",
        "type": "copy-file",
        "source": "src/hooks/sync-check.py",
        "destination": "dst/hooks/sync-check.py",
        "check_on_stop": True,
    }])

    msg = parse_msg(run_sync(root))
    if "rebuilt:" in msg and "hooks/sync-check.py" in msg:
        ok("systemMessage contains 'rebuilt:' and the drifted target name")
    else:
        fail_t(f"expected 'rebuilt:' and 'hooks/sync-check.py' in msg; got: {msg!r}")

    # ---- t2: multiple drifted targets — all names appear, comma-joined ----
    print()
    print("=== t2: multiple drifted targets — all names appear, comma-joined ===")
    root = make_git_repo()
    tmproots.append(root)

    write_file(os.path.join(root, "src/a.py"), "A source\n")
    write_file(os.path.join(root, "dst/a.py"), "A destination stale\n")
    write_file(os.path.join(root, "src/b.json"), "B source\n")
    write_file(os.path.join(root, "dst/b.json"), "B destination stale\n")

    write_contract(root, [
        {
            "name": "hooks/a.py",
            "type": "copy-file",
            "source": "src/a.py",
            "destination": "dst/a.py",
            "check_on_stop": True,
        },
        {
            "name": "settings/b.json",
            "type": "copy-file",
            "source": "src/b.json",
            "destination": "dst/b.json",
            "check_on_stop": True,
        },
    ])

    msg = parse_msg(run_sync(root))
    if "rebuilt:" in msg and "hooks/a.py" in msg and "settings/b.json" in msg:
        ok("systemMessage names both drifted targets")
    else:
        fail_t(f"expected both 'hooks/a.py' and 'settings/b.json' in msg; got: {msg!r}")

    # comma-joined: the two names must appear separated by a comma
    if "hooks/a.py, settings/b.json" in msg or "settings/b.json, hooks/a.py" in msg:
        ok("drifted target names appear comma-joined")
    else:
        fail_t(f"target names not comma-joined; got: {msg!r}")

    # ---- t3: zero drift — no surface-drift line ----
    print()
    print("=== t3: zero drift (sources match destinations) — no surface-drift line ===")
    root = make_git_repo()
    tmproots.append(root)

    write_file(os.path.join(root, "src/clean.py"), "identical content\n")
    write_file(os.path.join(root, "dst/clean.py"), "identical content\n")

    write_contract(root, [{
        "name": "hooks/clean.py",
        "type": "copy-file",
        "source": "src/clean.py",
        "destination": "dst/clean.py",
        "check_on_stop": True,
    }])

    out = run_sync(root)
    msg = parse_msg(out)
    if "Surface drift detected" not in msg and "rebuilt:" not in msg:
        ok("no surface-drift line emitted when sources match destinations")
    else:
        fail_t(f"unexpected surface-drift line emitted on clean repo; got: {msg!r}")

    # ---- t4: drift but check_on_stop=false — not flagged ----
    print()
    print("=== t4: check_on_stop=false drift is ignored ===")
    root = make_git_repo()
    tmproots.append(root)

    write_file(os.path.join(root, "src/optional.py"), "src\n")
    write_file(os.path.join(root, "dst/optional.py"), "dst stale\n")

    write_contract(root, [{
        "name": "optional/optional.py",
        "type": "copy-file",
        "source": "src/optional.py",
        "destination": "dst/optional.py",
        "check_on_stop": False,
    }])

    msg = parse_msg(run_sync(root))
    if "rebuilt:" not in msg and "optional/optional.py" not in msg:
        ok("check_on_stop=false target is not flagged as drifted")
    else:
        fail_t(f"check_on_stop=false target wrongly flagged; got: {msg!r}")

finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
