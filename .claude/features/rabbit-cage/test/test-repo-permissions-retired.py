#!/usr/bin/env python3
"""rabbit-cage e2e — the dead `permissions` lock/unlock configurable is retired (#366).

The `permissions` configurable (subcommand `permissions`, actions `lock`/`unlock`,
backed by `scripts/repo-permissions.py`) was a post-clone chmod drift guard over
`archive/` + `test/` that was never invoked in practice. Issue #366 retires it
(Designed Deprecation). This e2e pins the removed state so it cannot silently
return.

CRITICAL: this targets ONLY the dead repo-permissions `permissions` configurable.
The ACTIVE `bypass-permissions` configurable (backed by `permissions.defaultMode`)
MUST remain present and untouched — this test asserts that too, so a careless
removal of the wrong block fails here.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when rabbit-cage's configuration surface is tracked by a
structured schema that makes per-artifact retirement self-evident.
"""
import json
import os
import sys

CAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


print("test-repo-permissions-retired.py")

# t1 — scripts/repo-permissions.py is absent.
script_path = os.path.join(CAGE_DIR, "scripts", "repo-permissions.py")
if not os.path.exists(script_path):
    ok(1, "scripts/repo-permissions.py is absent")
else:
    fail_t(1, "scripts/repo-permissions.py still present — should be deleted (#366)")

# t2 — the unit suite test/test-repo-permissions.py is absent.
old_suite = os.path.join(CAGE_DIR, "test", "test-repo-permissions.py")
if not os.path.exists(old_suite):
    ok(2, "test/test-repo-permissions.py is absent")
else:
    fail_t(2, "test/test-repo-permissions.py still present — should be deleted (#366)")

# t3 — test/run.py does not wire test-repo-permissions.py.
run_py = os.path.join(CAGE_DIR, "test", "run.py")
with open(run_py) as fh:
    run_body = fh.read()
if "test-repo-permissions.py" not in run_body:
    ok(3, "test/run.py does not reference test-repo-permissions.py")
else:
    fail_t(3, "test/run.py still wires test-repo-permissions.py — should be removed (#366)")

# Load feature.json once for the configurable assertions.
with open(os.path.join(CAGE_DIR, "feature.json")) as fh:
    feature = json.load(fh)
configuration = feature.get("configuration", [])

# t4 — no configurable references scripts/repo-permissions.py anywhere in its body.
blob = json.dumps(configuration)
if "repo-permissions.py" not in blob:
    ok(4, "no configuration[] entry references scripts/repo-permissions.py")
else:
    fail_t(4, "a configuration[] entry still references scripts/repo-permissions.py (#366)")

# t5 — no configurable has subcommand == "permissions" (the dead one).
dead = [c for c in configuration if c.get("subcommand") == "permissions"]
if not dead:
    ok(5, "no configurable with subcommand == 'permissions' remains")
else:
    fail_t(5, f"configurable with subcommand == 'permissions' still present: {dead!r}")

# t6 — the ACTIVE bypass-permissions configurable is STILL present (regression guard).
bypass = [c for c in configuration if c.get("subcommand") == "bypass-permissions"]
if len(bypass) == 1:
    ok(6, "active bypass-permissions configurable is intact")
else:
    fail_t(6, f"bypass-permissions configurable must remain (found {len(bypass)}) — do NOT remove the active one")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
