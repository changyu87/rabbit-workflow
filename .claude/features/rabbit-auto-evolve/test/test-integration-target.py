#!/usr/bin/env python3
"""test-integration-target.py — e2e tests for the integration-target
abstraction (Inv 61).

The dev->main cutover is complete and the coexistence window has closed: `main`
is now the SOLE accepted integration target. `resolve_target()` is
deterministic — it returns `main` with no environment read — and the
`RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET` env var no longer exists, so setting it
has NO effect.

This suite drives the module BOTH as an importable library (the surface the
sibling phase scripts consume) and as a small CLI (`integration_target.py`),
covering:
  - resolve_target() returns main deterministically
  - the (removed) env var is IGNORED — setting it does not change the result
  - the accepted-set is exactly {main}
  - is_default_branch: main is the default branch, dev is not
"""

import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "integration_target.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _load_module():
    spec = importlib.util.spec_from_file_location("integration_target", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(env, *args):
    return subprocess.run(
        [sys.executable, MODULE, *args],
        env=env, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# Library surface
# ---------------------------------------------------------------------------
it = _load_module()

# resolve_target() returns main — deterministic, no environment read.
saved = os.environ.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
try:
    if it.resolve_target() != "main":
        fail(f"lib-default: resolve_target() {it.resolve_target()!r} != 'main'")
    else:
        ok("lib-default: resolve_target() returns 'main'")
finally:
    if saved is not None:
        os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = saved

# The old env var is IGNORED: setting it to 'dev' does NOT change the result.
os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = "dev"
try:
    if it.resolve_target() != "main":
        fail(f"lib-env-ignored: resolve_target() {it.resolve_target()!r} != "
             f"'main' (the removed env var must be ignored)")
    else:
        ok("lib-env-ignored: the removed env var has no effect")
finally:
    del os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"]

# Accepted set is exactly {main}.
if tuple(it.accepted_targets()) != ("main",):
    fail(f"lib-accepted: accepted_targets() {it.accepted_targets()!r} "
         f"!= ('main',)")
else:
    ok("lib-accepted: accepted_targets() == ('main',)")

# is_default_branch: main is the default branch, dev is not.
if not it.is_default_branch("main"):
    fail("lib-default-branch: is_default_branch('main') should be True")
elif it.is_default_branch("dev"):
    fail("lib-default-branch: is_default_branch('dev') should be False")
else:
    ok("lib-default-branch: main is the default branch, dev is not")


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------
proc = _run_cli(os.environ.copy(), "--help")
if proc.returncode != 0:
    fail(f"cli-help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
elif "usage" not in (proc.stdout + proc.stderr).lower():
    fail(f"cli-help: 'usage' missing; stdout={proc.stdout!r}")
else:
    ok("cli-help: --help exits 0 with usage text")

# CLI prints the resolved target (main).
env = os.environ.copy()
env.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
proc = _run_cli(env)
if proc.returncode != 0:
    fail(f"cli-default: exit {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout.strip() != "main":
    fail(f"cli-default: stdout {proc.stdout.strip()!r} != 'main'")
else:
    ok("cli-default: prints 'main'")

# The removed env var is IGNORED at the CLI too: setting it to 'dev' still
# prints 'main' and exits 0 (no override path remains to reject it).
env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = "dev"
proc = _run_cli(env)
if proc.returncode != 0:
    fail(f"cli-env-ignored: exit {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout.strip() != "main":
    fail(f"cli-env-ignored: stdout {proc.stdout.strip()!r} != 'main' "
         f"(the removed env var must be ignored)")
else:
    ok("cli-env-ignored: prints 'main' even with the removed env var set")


sys.exit(FAIL)
