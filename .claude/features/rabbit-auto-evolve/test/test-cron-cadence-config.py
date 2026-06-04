#!/usr/bin/env python3
"""test-cron-cadence-config.py — e2e tests for the OPERATIONAL, configurable
tick cadence (issue #722).

#723 made the cadence single-sourced (`CADENCE_MINUTES = 30` in
install-cron.py, with both scheduler paths deriving from it) but it was still
HARDCODED — tuning it required a source edit + redeploy. #722 makes the cadence
operational config: an operator sets it WITHOUT touching source, with 30
(`*/30`) as the default, both scheduler paths reading the SAME configured
value, and an invalid value REJECTED.

These tests run install-cron.py end-to-end through the SAME fake-crontab shim
used by test-cron-trigger.py (the tests MUST NOT touch the real user crontab),
and additionally drive the restricted-host path (which emits the
`CronCreate`-fallback heartbeat) so BOTH scheduler paths are asserted to read
the same configured cadence.

Resolution precedence asserted:
  RABBIT_AUTO_EVOLVE_CADENCE env var
    > `cadence_minutes` in <state_dir>/auto-evolve-cadence-config.json
    > the CADENCE_MINUTES default (30)

Scenarios:
  1) DEFAULT — no env, no config file → system-cron entry is `*/30 * * * *`
     and the fallback heartbeat is `13,43 * * * *` (unchanged from #723).
  2) CONFIG-FILE override — cadence_minutes:15 in the state-dir config file →
     system-cron `*/15 * * * *` AND fallback heartbeat `13,28,43,58 * * * *`
     (BOTH paths move together).
  3) ENV override — RABBIT_AUTO_EVOLVE_CADENCE=20 → system-cron `*/20 * * * *`;
     env WINS over a (different) config-file value.
  4) INVALID values — non-integer, 0, 60, negative → REJECTED: install-cron.py
     does NOT install a nonsense cron line; it falls back to the */30 default
     and emits a branded warning. (Exit 0; the mode flip is never blocked.)
  5) Unit-level: _configured_cadence() honors the precedence and validation
     directly (env > config file > default; invalid → default).
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
INSTALL = str(SCRIPTS / "install-cron.py")

ENTRY_TOKEN = "tick-headless.py"
CONFIG_NAME = "auto-evolve-cadence-config.json"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load_install_cron():
    spec = importlib.util.spec_from_file_location(
        "install_cron", str(SCRIPTS / "install-cron.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_fake_crontab(dirpath):
    """A fake `crontab` backed by <dirpath>/crontab.txt (same shim shape as
    test-cron-trigger.py)."""
    crondata = os.path.join(dirpath, "crontab.txt")
    shim = os.path.join(dirpath, "crontab")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys, os
            DATA = {crondata!r}
            args = sys.argv[1:]
            if args == ["-l"]:
                if not os.path.isfile(DATA):
                    sys.stderr.write("no crontab for testuser\\n")
                    sys.exit(1)
                with open(DATA) as fh:
                    sys.stdout.write(fh.read())
                sys.exit(0)
            if args == ["-"]:
                content = sys.stdin.read()
                with open(DATA, "w") as fh:
                    fh.write(content)
                sys.exit(0)
            sys.stderr.write("fake crontab: unsupported args %r\\n" % (args,))
            sys.exit(2)
            """))
    os.chmod(shim, 0o755)
    return shim, crondata


def make_restricted_crontab(dirpath):
    """A fake `crontab` that simulates an administratively restricted host
    (drives install-cron.py down the CronCreate-fallback heartbeat path)."""
    shim = os.path.join(dirpath, "crontab")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys
            sys.stderr.write(
                "You (testuser) are not allowed to use this program "
                "(crontab)\\n")
            sys.exit(1)
            """))
    os.chmod(shim, 0o755)
    return shim


def run_install(repo_root, shim, state_dir=None, cadence_env=None):
    env = os.environ.copy()
    env["RABBIT_CRONTAB_CMD"] = shim
    if state_dir is not None:
        env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    else:
        env.pop("RABBIT_AUTO_EVOLVE_STATE_DIR", None)
    if cadence_env is not None:
        env["RABBIT_AUTO_EVOLVE_CADENCE"] = cadence_env
    else:
        env.pop("RABBIT_AUTO_EVOLVE_CADENCE", None)
    return subprocess.run(
        [sys.executable, INSTALL],
        cwd=repo_root, capture_output=True, text=True, env=env,
    )


def write_config(state_dir, value):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, CONFIG_NAME), "w") as f:
        json.dump({"cadence_minutes": value}, f)


def read_cron(crondata):
    if not os.path.isfile(crondata):
        return ""
    with open(crondata) as f:
        return f.read()


def heartbeat_signal(proc):
    """Parse the croncreate-fallback JSON signal off install-cron.py stdout."""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and "croncreate" in line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return None
    return None


# ---------------------------------------------------------------------------
# Scenario 1 — DEFAULT cadence (no env, no config file)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(d, "state")
    os.makedirs(repo_root)
    proc = run_install(repo_root, shim, state_dir=state_dir)
    if proc.returncode != 0:
        fail(f"1: default install exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("1: default install exits 0")
    body = read_cron(crondata)
    if "*/30 * * * *" in body:
        ok("1: default system-cron entry is */30")
    else:
        fail(f"1: expected '*/30 * * * *' default; got {body!r}")

    # Default fallback heartbeat (restricted host) is 13,43.
    rshim = make_restricted_crontab(d)
    rproc = run_install(repo_root, rshim, state_dir=state_dir)
    sig = heartbeat_signal(rproc)
    if sig and sig.get("cron") == "13,43 * * * *":
        ok("1: default fallback heartbeat is 13,43")
    else:
        fail(f"1: expected default heartbeat '13,43 * * * *'; got {sig!r}")


# ---------------------------------------------------------------------------
# Scenario 2 — CONFIG-FILE override moves BOTH paths together
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(d, "state")
    os.makedirs(repo_root)
    write_config(state_dir, 15)

    proc = run_install(repo_root, shim, state_dir=state_dir)
    body = read_cron(crondata)
    if "*/15 * * * *" in body:
        ok("2: config-file cadence=15 → system-cron */15")
    else:
        fail(f"2: expected '*/15 * * * *' from config file; got {body!r}")
    if "*/30" not in body:
        ok("2: the default */30 is NOT installed when config overrides it")
    else:
        fail(f"2: stale default */30 present alongside override; got {body!r}")

    # The fallback heartbeat for cadence 15 derives to 13,28,43,58.
    rshim = make_restricted_crontab(d)
    rproc = run_install(repo_root, rshim, state_dir=state_dir)
    sig = heartbeat_signal(rproc)
    if sig and sig.get("cron") == "13,28,43,58 * * * *":
        ok("2: config-file cadence=15 → fallback heartbeat 13,28,43,58 (BOTH "
           "paths move)")
    else:
        fail(f"2: expected heartbeat '13,28,43,58 * * * *' for cadence 15; "
             f"got {sig!r}")


# ---------------------------------------------------------------------------
# Scenario 3 — ENV override wins over a different config-file value
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    shim, crondata = make_fake_crontab(d)
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(d, "state")
    os.makedirs(repo_root)
    write_config(state_dir, 15)  # config says 15...

    proc = run_install(repo_root, shim, state_dir=state_dir, cadence_env="20")
    body = read_cron(crondata)
    if "*/20 * * * *" in body:
        ok("3: env RABBIT_AUTO_EVOLVE_CADENCE=20 wins → system-cron */20")
    else:
        fail(f"3: expected env override '*/20 * * * *'; got {body!r}")
    if "*/15" not in body:
        ok("3: the config-file value (15) is overridden by the env var")
    else:
        fail(f"3: config-file */15 leaked despite env override; got {body!r}")


# ---------------------------------------------------------------------------
# Scenario 4 — INVALID values are rejected (fall back to */30, never nonsense)
# ---------------------------------------------------------------------------
for label, env_val, cfg_val in (
    ("non-integer env", "abc", None),
    ("zero env", "0", None),
    ("sixty env", "60", None),
    ("negative env", "-5", None),
    ("non-integer config", None, "xyz"),
    ("zero config", None, 0),
    ("out-of-range config", None, 90),
):
    with tempfile.TemporaryDirectory() as d:
        shim, crondata = make_fake_crontab(d)
        repo_root = os.path.join(d, "repo")
        state_dir = os.path.join(d, "state")
        os.makedirs(repo_root)
        if cfg_val is not None:
            write_config(state_dir, cfg_val)
        proc = run_install(repo_root, shim, state_dir=state_dir,
                           cadence_env=env_val)
        if proc.returncode != 0:
            fail(f"4 [{label}]: install exit {proc.returncode} "
                 f"(should not block the mode flip); stderr={proc.stderr!r}")
            continue
        body = read_cron(crondata)
        if "*/30 * * * *" in body:
            ok(f"4 [{label}]: rejected → fell back to the */30 default")
        else:
            fail(f"4 [{label}]: did NOT fall back to */30; got {body!r}")
        # A branded warning should mention the invalid/ignored cadence.
        out = (proc.stdout + proc.stderr).lower()
        if "cadence" in out and ("invalid" in out or "ignor" in out
                                 or "default" in out):
            ok(f"4 [{label}]: emitted a branded cadence-warning")
        else:
            fail(f"4 [{label}]: expected a branded cadence warning; "
                 f"got {(proc.stdout + proc.stderr)!r}")


# ---------------------------------------------------------------------------
# Scenario 5 — unit-level _configured_cadence() precedence + validation
# ---------------------------------------------------------------------------
mod = load_install_cron()
if not hasattr(mod, "_configured_cadence") \
        or not callable(mod._configured_cadence):
    fail("5: install-cron.py exposes no _configured_cadence() resolver")
    sys.exit(FAIL)
ok("5: install-cron.py exposes _configured_cadence()")

_saved = {k: os.environ.get(k) for k in
          ("RABBIT_AUTO_EVOLVE_CADENCE", "RABBIT_AUTO_EVOLVE_STATE_DIR")}


def _restore_env():
    for k, v in _saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, "state")
    os.environ["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    os.environ.pop("RABBIT_AUTO_EVOLVE_CADENCE", None)

    # No env, no config → default.
    if mod._configured_cadence() == mod.CADENCE_MINUTES:
        ok("5: no env/config → CADENCE_MINUTES default")
    else:
        fail(f"5: default resolution wrong: {mod._configured_cadence()!r}")

    # Config file only.
    write_config(state_dir, 12)
    if mod._configured_cadence() == 12:
        ok("5: config-file value resolved")
    else:
        fail(f"5: config-file resolution wrong: {mod._configured_cadence()!r}")

    # Env beats config.
    os.environ["RABBIT_AUTO_EVOLVE_CADENCE"] = "25"
    if mod._configured_cadence() == 25:
        ok("5: env wins over config file")
    else:
        fail(f"5: env precedence wrong: {mod._configured_cadence()!r}")

    # Invalid env → falls back (to config value 12, the next valid source).
    os.environ["RABBIT_AUTO_EVOLVE_CADENCE"] = "nope"
    if mod._configured_cadence() == 12:
        ok("5: invalid env falls through to the config-file value")
    else:
        fail(f"5: invalid-env fallthrough wrong: {mod._configured_cadence()!r}")

    # Invalid env + invalid config → default.
    write_config(state_dir, 0)
    if mod._configured_cadence() == mod.CADENCE_MINUTES:
        ok("5: invalid env + invalid config → CADENCE_MINUTES default")
    else:
        fail(f"5: all-invalid fallback wrong: {mod._configured_cadence()!r}")

_restore_env()

sys.exit(FAIL)
