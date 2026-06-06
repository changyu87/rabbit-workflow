#!/usr/bin/env python3
"""test-integration-target.py — e2e tests for the integration-target
abstraction (Inv 61).

The autonomous-evolve loop integrates merged work into a single resolved
"integration target" branch. During the dev<->main coexistence window BOTH
`dev` and `main` are accepted; the resolved target defaults to `dev` (the live
behavior until the admin cutover flips the default to `main`) and can be
overridden via the RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET env var.

This suite drives the module BOTH as an importable library (the surface the
sibling phase scripts consume) and as a small CLI (`integration_target.py`),
covering:
  - default resolution → dev
  - env-var override → main
  - an unrecognized override is rejected (neither dev nor main)
  - the coexistence accepted-set is exactly {dev, main}
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

# Default (no env override) resolves to dev — the live coexistence default.
saved = os.environ.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
try:
    if it.resolve_target() != "dev":
        fail(f"lib-default: resolve_target() {it.resolve_target()!r} != 'dev'")
    else:
        ok("lib-default: resolve_target() defaults to 'dev'")
finally:
    if saved is not None:
        os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = saved

# Env override → main.
os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = "main"
try:
    if it.resolve_target() != "main":
        fail(f"lib-override: resolve_target() {it.resolve_target()!r} != 'main'")
    else:
        ok("lib-override: env override resolves to 'main'")
finally:
    del os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"]

# Unrecognized override is rejected (must be one of the coexistence set).
os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = "release/x"
try:
    try:
        it.resolve_target()
        fail("lib-bad-override: an unrecognized target was not rejected")
    except ValueError:
        ok("lib-bad-override: an unrecognized target raises ValueError")
finally:
    del os.environ["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"]

# Coexistence accepted set is exactly {dev, main}.
if set(it.accepted_targets()) != {"dev", "main"}:
    fail(f"lib-accepted: accepted_targets() {it.accepted_targets()!r} "
         f"!= {{dev, main}}")
else:
    ok("lib-accepted: accepted_targets() == {dev, main}")

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

# CLI prints the resolved target (default dev).
env = os.environ.copy()
env.pop("RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET", None)
proc = _run_cli(env)
if proc.returncode != 0:
    fail(f"cli-default: exit {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout.strip() != "dev":
    fail(f"cli-default: stdout {proc.stdout.strip()!r} != 'dev'")
else:
    ok("cli-default: prints 'dev' by default")

env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = "main"
proc = _run_cli(env)
if proc.returncode != 0:
    fail(f"cli-override: exit {proc.returncode}; stderr={proc.stderr!r}")
elif proc.stdout.strip() != "main":
    fail(f"cli-override: stdout {proc.stdout.strip()!r} != 'main'")
else:
    ok("cli-override: prints 'main' under env override")

env["RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET"] = "garbage"
proc = _run_cli(env)
if proc.returncode == 0:
    fail("cli-bad-override: an unrecognized target should exit non-zero")
else:
    ok("cli-bad-override: an unrecognized target exits non-zero")


sys.exit(FAIL)
