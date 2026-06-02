#!/usr/bin/env python3
"""test-set-evolve-mode.py — e2e tests for scripts/set-evolve-mode.py
(Inv 1: compound mutator with rollback semantics and idempotency).

Exercises the four spec-mandated scenarios:
  A) `on` from clean state — all three side effects appear.
  B) `off` from on state — all three side effects revert.
  C) Failure at step 2 — rollback removes step 1's marker; non-zero exit;
     stderr names the failed step.
  D) Idempotency — `on`-from-`on` and `off`-from-`off` are clean no-ops.

Uses tempfile.TemporaryDirectory() fixtures per rabbit-config Inv 17
isolation pattern; invokes the script as a subprocess with cwd=tmp so the
script's `repo_root = os.getcwd()` resolution targets the fixture.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "set-evolve-mode.py"))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
CONTRACT_DIR = os.path.join(REPO_ROOT, ".claude", "features", "contract")

MARKER_BYPASS = ".rabbit-human-approval-bypass"
MARKER_ACTIVE = ".rabbit-auto-evolve-active"
# Inv 1 v0.7.1 (#371): the four loop-runtime markers that `off` must also
# delete (innermost first) before reversing the activation mutations.
LOOP_RUNTIME_MARKERS = [
    ".rabbit-auto-evolve-running",
    ".rabbit-auto-evolve-stop-requested",
    ".rabbit-auto-evolve-restart-needed",
    ".rabbit-auto-evolve-aborted",
]
SETTINGS = os.path.join(".claude", "settings.local.json")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run_script(cwd, *args, env_extra=None):
    """Run the script from cwd. Returns CompletedProcess."""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def write_settings(root, mapping):
    """Write .claude/settings.local.json with given mapping."""
    path = os.path.join(root, SETTINGS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(mapping, f, indent=2)


def read_settings(root):
    path = os.path.join(root, SETTINGS)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Scenario A — `on` from clean state
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    proc = run_script(root, "on")
    if proc.returncode != 0:
        fail(f"A: expected exit 0 from `on`, got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("A: `on` exited 0")
    if not os.path.isfile(os.path.join(root, MARKER_BYPASS)):
        fail(f"A: expected {MARKER_BYPASS} to exist after `on`")
    else:
        with open(os.path.join(root, MARKER_BYPASS)) as f:
            content = f.read()
        if content != "session":
            fail(f"A: expected {MARKER_BYPASS} content='session', got {content!r}")
        else:
            ok(f"A: {MARKER_BYPASS} written with content 'session'")
    if not os.path.isfile(os.path.join(root, MARKER_ACTIVE)):
        fail(f"A: expected {MARKER_ACTIVE} to exist after `on`")
    else:
        ok(f"A: {MARKER_ACTIVE} written")
    data = read_settings(root)
    if data is None:
        fail(f"A: expected {SETTINGS} to exist after `on`")
    elif data.get("permissions", {}).get("defaultMode") != "bypassPermissions":
        fail(f"A: expected permissions.defaultMode='bypassPermissions', got {data!r}")
    else:
        ok("A: permissions.defaultMode = 'bypassPermissions'")


# ---------------------------------------------------------------------------
# Scenario B — `off` from on state
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    # Bring to on state first
    proc_on = run_script(root, "on")
    if proc_on.returncode != 0:
        fail(f"B: pre-setup `on` failed: {proc_on.stderr!r}")
    proc = run_script(root, "off")
    if proc.returncode != 0:
        fail(f"B: expected exit 0 from `off`, got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("B: `off` exited 0")
    if os.path.exists(os.path.join(root, MARKER_BYPASS)):
        fail(f"B: expected {MARKER_BYPASS} to be removed after `off`")
    else:
        ok(f"B: {MARKER_BYPASS} removed")
    if os.path.exists(os.path.join(root, MARKER_ACTIVE)):
        fail(f"B: expected {MARKER_ACTIVE} to be removed after `off`")
    else:
        ok(f"B: {MARKER_ACTIVE} removed")
    data = read_settings(root)
    # settings file may still exist (with permissions block emptied) — what
    # matters is that defaultMode key is gone.
    if data is not None and data.get("permissions", {}).get("defaultMode") is not None:
        fail(f"B: expected permissions.defaultMode key gone, got {data!r}")
    else:
        ok("B: permissions.defaultMode deleted")


# ---------------------------------------------------------------------------
# Scenario C — Failure simulation at step 2 (set_json_key raises)
# ---------------------------------------------------------------------------
# We inject a sitecustomize.py into a tmp dir on PYTHONPATH that monkey-patches
# contract.lib.mutation.set_json_key to raise. The script imports the module
# fresh in its own process, so this is the cleanest way to force a step-2
# failure without modifying the script under test.
with tempfile.TemporaryDirectory() as root:
    with tempfile.TemporaryDirectory() as pythonpath_dir:
        sitecustomize = os.path.join(pythonpath_dir, "sitecustomize.py")
        with open(sitecustomize, "w") as f:
            f.write(textwrap.dedent(f"""
                import sys, os
                _contract_dir = {CONTRACT_DIR!r}
                if _contract_dir not in sys.path:
                    sys.path.insert(0, _contract_dir)
                from lib import mutation as _m
                def _raise(*a, **kw):
                    raise RuntimeError("INJECTED step-2 failure")
                _m.set_json_key = _raise
            """).lstrip())
        env_extra = {"PYTHONPATH": pythonpath_dir}
        proc = run_script(root, "on", env_extra=env_extra)
        if proc.returncode == 0:
            fail(f"C: expected non-zero exit on step-2 failure, got 0; stderr={proc.stderr!r}")
        else:
            ok(f"C: non-zero exit ({proc.returncode}) on step-2 failure")
        # Step 1's marker must have been rolled back.
        if os.path.exists(os.path.join(root, MARKER_BYPASS)):
            fail(f"C: expected {MARKER_BYPASS} to be rolled back, but it still exists")
        else:
            ok(f"C: {MARKER_BYPASS} rolled back after step-2 failure")
        # Step 3's marker must NOT exist (never reached).
        if os.path.exists(os.path.join(root, MARKER_ACTIVE)):
            fail(f"C: {MARKER_ACTIVE} should not exist after step-2 failure")
        else:
            ok(f"C: {MARKER_ACTIVE} not present (step never ran)")
        # stderr must name the failed step.
        if "step 2" not in proc.stderr.lower() and "set_json_key" not in proc.stderr.lower():
            fail(f"C: stderr should name the failed step (step 2 / set_json_key); got: {proc.stderr!r}")
        else:
            ok("C: stderr names the failed step")


# ---------------------------------------------------------------------------
# Scenario D — Idempotency
# ---------------------------------------------------------------------------
# on-from-on
with tempfile.TemporaryDirectory() as root:
    p1 = run_script(root, "on")
    if p1.returncode != 0:
        fail(f"D: pre-setup `on` failed: {p1.stderr!r}")
    p2 = run_script(root, "on")
    if p2.returncode != 0:
        fail(f"D: `on`-from-`on` should be clean no-op, got exit {p2.returncode}; stderr={p2.stderr!r}")
    else:
        ok("D: `on`-from-`on` clean no-op (exit 0)")
    # State unchanged
    if not os.path.isfile(os.path.join(root, MARKER_BYPASS)):
        fail("D: state changed after on-from-on (bypass marker missing)")
    data = read_settings(root)
    if data is None or data.get("permissions", {}).get("defaultMode") != "bypassPermissions":
        fail("D: state changed after on-from-on (defaultMode wrong)")
    if not os.path.isfile(os.path.join(root, MARKER_ACTIVE)):
        fail("D: state changed after on-from-on (active marker missing)")

# off-from-off
with tempfile.TemporaryDirectory() as root:
    # Clean state — invoke off immediately
    p = run_script(root, "off")
    if p.returncode != 0:
        fail(f"D: `off`-from-`off` (clean) should be clean no-op, got exit {p.returncode}; stderr={p.stderr!r}")
    else:
        ok("D: `off`-from-`off` clean no-op (exit 0)")
    if os.path.exists(os.path.join(root, MARKER_BYPASS)):
        fail("D: bypass marker should not appear from off-from-off")
    if os.path.exists(os.path.join(root, MARKER_ACTIVE)):
        fail("D: active marker should not appear from off-from-off")


# ---------------------------------------------------------------------------
# Scenario E — `off` full teardown including 4 loop-runtime markers
# (Inv 1 v0.7.1 / issue #371). Pre-seed all 5 markers + settings, then run
# `off`; assert all 5 marker files gone, settings.local.json has
# permissions.defaultMode removed, exit 0.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    # Seed activation state
    with open(os.path.join(root, MARKER_BYPASS), "w") as f:
        f.write("session")
    with open(os.path.join(root, MARKER_ACTIVE), "w") as f:
        f.write("")
    write_settings(root, {"permissions": {"defaultMode": "bypassPermissions"}})
    # Seed all 4 loop-runtime markers
    for m in LOOP_RUNTIME_MARKERS:
        with open(os.path.join(root, m), "w") as f:
            f.write("session")

    proc = run_script(root, "off")
    if proc.returncode != 0:
        fail(f"E: expected exit 0 from full-teardown `off`, got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("E: full-teardown `off` exited 0")
    # All five marker files must be gone.
    all_markers = [MARKER_BYPASS, MARKER_ACTIVE, *LOOP_RUNTIME_MARKERS]
    for m in all_markers:
        if os.path.exists(os.path.join(root, m)):
            fail(f"E: expected {m} to be removed after full-teardown `off`")
        else:
            ok(f"E: {m} removed")
    data = read_settings(root)
    if data is not None and data.get("permissions", {}).get("defaultMode") is not None:
        fail(f"E: expected permissions.defaultMode key gone, got {data!r}")
    else:
        ok("E: permissions.defaultMode deleted")


# ---------------------------------------------------------------------------
# Scenario F — partial-state `off`: only `.rabbit-auto-evolve-running` present
# (no active marker, no bypass marker, no settings entry). `off` must succeed,
# delete the running marker, no error. Inv 1 v0.7.1: runtime-marker deletion
# is idempotent (missing markers are no-ops).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    running = os.path.join(root, ".rabbit-auto-evolve-running")
    with open(running, "w") as f:
        f.write("session")

    proc = run_script(root, "off")
    if proc.returncode != 0:
        fail(f"F: expected exit 0 from partial-state `off`, got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("F: partial-state `off` exited 0")
    if os.path.exists(running):
        fail("F: expected .rabbit-auto-evolve-running to be removed after partial-state `off`")
    else:
        ok("F: .rabbit-auto-evolve-running removed")
    # The other 3 loop-runtime markers were never present — must still be absent.
    for m in [".rabbit-auto-evolve-stop-requested",
              ".rabbit-auto-evolve-restart-needed",
              ".rabbit-auto-evolve-aborted"]:
        if os.path.exists(os.path.join(root, m)):
            fail(f"F: {m} should not exist after partial-state `off`")


# ---------------------------------------------------------------------------
# Scenario G — Branded confirmation on `on` success (Inv 1 v0.7.4 / issue #377).
# `on` success must emit two branded rabbit_print lines to stdout: line 1 red
# with `AUTONOMOUS-EVOLVE MODE CONFIGURED` + `restart Claude`; line 2 yellow
# with `/rabbit-auto-evolve start`. Both lines must carry the `[🐇 rabbit 🐇]`
# brand prefix so the message matches the SessionStart banner's visual weight
# (the prior flat `set-evolve-mode: on OK` line was easy to miss).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    proc = run_script(root, "on")
    if proc.returncode != 0:
        fail(f"G: pre-setup `on` failed: {proc.stderr!r}")
    out = proc.stdout
    if "[\U0001f407 rabbit \U0001f407]" not in out:
        fail(f"G: stdout missing brand prefix '[\U0001f407 rabbit \U0001f407]'; got: {out!r}")
    else:
        ok("G: `on` stdout carries [\U0001f407 rabbit \U0001f407] brand prefix")
    # Both lines must carry the brand — assert at least two occurrences.
    _brand = "[\U0001f407 rabbit \U0001f407]"
    _brand_count = out.count(_brand)
    if _brand_count < 2:
        fail(f"G: expected >= 2 brand prefixes (one per line), got {_brand_count}; stdout: {out!r}")
    else:
        ok("G: `on` stdout carries brand prefix on both lines")
    if "AUTONOMOUS-EVOLVE MODE CONFIGURED" not in out:
        fail(f"G: stdout missing 'AUTONOMOUS-EVOLVE MODE CONFIGURED'; got: {out!r}")
    else:
        ok("G: `on` stdout contains 'AUTONOMOUS-EVOLVE MODE CONFIGURED'")
    if "restart Claude" not in out:
        fail(f"G: stdout missing 'restart Claude'; got: {out!r}")
    else:
        ok("G: `on` stdout contains 'restart Claude' instruction")
    if "/rabbit-auto-evolve start" not in out:
        fail(f"G: stdout missing '/rabbit-auto-evolve start'; got: {out!r}")
    else:
        ok("G: `on` stdout contains '/rabbit-auto-evolve start' command")


# ---------------------------------------------------------------------------
# Scenario H — Branded confirmation on `off` success (Inv 1 v0.7.4 / issue #377).
# `off` success must emit one branded rabbit_print line to stdout: green with
# `deactivated` and the `[🐇 rabbit 🐇]` brand prefix.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    # Bring to on state first so off has real work to do
    proc_on = run_script(root, "on")
    if proc_on.returncode != 0:
        fail(f"H: pre-setup `on` failed: {proc_on.stderr!r}")
    proc = run_script(root, "off")
    if proc.returncode != 0:
        fail(f"H: `off` failed: {proc.stderr!r}")
    out = proc.stdout
    if "[\U0001f407 rabbit \U0001f407]" not in out:
        fail(f"H: stdout missing brand prefix '[\U0001f407 rabbit \U0001f407]'; got: {out!r}")
    else:
        ok("H: `off` stdout carries [\U0001f407 rabbit \U0001f407] brand prefix")
    if "deactivated" not in out:
        fail(f"H: stdout missing 'deactivated'; got: {out!r}")
    else:
        ok("H: `off` stdout contains 'deactivated'")


sys.exit(FAIL)
