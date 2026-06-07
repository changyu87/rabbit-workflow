#!/usr/bin/env python3
"""install-cron.py — install the system-cron entry that fires the headless tick.

Usage:
  install-cron.py            # idempotently install the tick-headless crontab entry

Per rabbit-auto-evolve spec.md Inv 32 (issue #414), the system cron is the
SOLE tick scheduler — the prior self-chained `ScheduleWakeup` was removed
entirely. This script installs ONE crontab entry of the form:

  */30 * * * * cd <repo_root> && python3
    .claude/features/rabbit-auto-evolve/scripts/tick-headless.py
    >> .rabbit/tick-headless.log 2>&1

using the `crontab -l` (read current) + append + `crontab -` (write back)
pattern. It is IDEMPOTENT: if an entry mentioning `tick-headless.py` already
exists in the user's crontab, this is a clean no-op (running twice yields
exactly one entry). Unrelated crontab lines are preserved verbatim.

`set-evolve-mode.py on` invokes this script after writing the three
activation markers.

The `crontab` binary is resolved via the `RABBIT_CRONTAB_CMD` env var when
set (so tests can inject a fake shim), else the literal `crontab`. The repo
root is resolved via `RABBIT_AUTO_EVOLVE_REPO_ROOT` when set, else
`os.getcwd()`.

Configurable cadence (issue #722): `CADENCE_MINUTES = 30` is the DEFAULT, not
a hard wire. The EFFECTIVE cadence is resolved by `_configured_cadence()` with
precedence env `RABBIT_AUTO_EVOLVE_CADENCE` > `cadence_minutes` in the OWN
state-dir config file `<state_dir>/auto-evolve-cadence-config.json` (state dir
via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else `<cwd>/.rabbit`, mirroring
`log-tick.py`'s own config; NOT rabbit-cage's `configuration` array nor
rabbit-config) > the `CADENCE_MINUTES` default. The resolved value is VALIDATED
as an integer in `1..59`; an invalid source is SKIPPED (next source wins) and,
when no source yields a valid value, the default is used. BOTH scheduler paths
derive their cron expression from the SAME resolved cadence: the system-cron
entry line and the `CronCreate`-fallback heartbeat. A rejected configured value
emits a branded warning but never blocks the install (exit 0).

Exit code: 0 on success (including the idempotent no-op). Non-zero only on a
genuine crontab read/write failure.

Restricted-host CronCreate fallback (issues #507, #521, spec Inv 32/34): on
hosts where the `crontab` binary is administratively restricted (e.g. "You
... are not allowed to use this program (crontab)"), this script DETECTS the
denial via detect-scheduler.py (distinguished from the legitimate empty "no
crontab for user" case) and falls back gracefully rather than failing
opaquely. It exits 0 and emits (a) a machine-readable JSON signal naming the
durable `CronCreate` heartbeat the DISPATCHER must create (a script cannot
call `CronCreate`) and (b) a branded `rabbit_print` line telling the user the
durable heartbeat will be set up on the next `/rabbit-auto-evolve start`. The
heartbeat cron expression avoids the :00/:30 minute marks per CronCreate
guidance. Cron remains the tick scheduler where available.

Version: 1.4.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys

ENTRY_TOKEN = "tick-headless.py"
TICK_SCRIPT = ".claude/features/rabbit-auto-evolve/scripts/tick-headless.py"
LOG_PATH = ".rabbit/tick-headless.log"

# ---------------------------------------------------------------------------
# SINGLE SOURCE OF TRUTH for the tick cadence (issue #723).
#
# `CADENCE_MINUTES` is the ONE codified cadence value. BOTH scheduler paths
# DERIVE their cron expression from it via the helpers below — there is no
# second independent literal. Change CADENCE_MINUTES and BOTH the system-cron
# `SCHEDULE` and the CronCreate-fallback `HEARTBEAT_EXPR` move together; the
# spec.md / SKILL.md literals are pinned to this source by
# test/test-cron-cadence-source.py so prose drift fails the gate.
# ---------------------------------------------------------------------------
CADENCE_MINUTES = 30
# The fallback heartbeat shifts off the :00/:30 marks per CronCreate guidance
# (issue #521) by adding this fixed offset to each derived minute mark.
HEARTBEAT_OFFSET = 13


def _cadence_minute_marks(cadence_minutes):
    """The within-hour minute marks for a sub-hour cadence: 0, c, 2c, ...
    below 60. For cadence 30 this is [0, 30]; for 15 it is [0, 15, 30, 45]."""
    return list(range(0, 60, cadence_minutes))


def _system_cron_expr(cadence_minutes):
    """Derive the system-cron expression for `cadence_minutes` (the path used
    by the `crontab` entry). Renders as the canonical `*/<n> * * * *` step
    form that fires on the :00/:30/... marks."""
    return f"*/{cadence_minutes} * * * *"


def _heartbeat_expr(cadence_minutes):
    """Derive the CronCreate-fallback heartbeat expression for the SAME
    `cadence_minutes` as the system-cron path, shifted off the :00/:30 marks
    by `HEARTBEAT_OFFSET` (CronCreate guidance, issue #521). For the default
    30-min cadence this yields `13,43 * * * *`."""
    shifted = sorted(
        (m + HEARTBEAT_OFFSET) % 60
        for m in _cadence_minute_marks(cadence_minutes)
    )
    return f"{','.join(str(m) for m in shifted)} * * * *"


SCHEDULE = _system_cron_expr(CADENCE_MINUTES)
HEARTBEAT_EXPR = _heartbeat_expr(CADENCE_MINUTES)

# ---------------------------------------------------------------------------
# OPERATIONAL cadence config (issue #722). The cadence above is the DEFAULT;
# an operator can tune it WITHOUT editing source via (in precedence order):
#   1. the `RABBIT_AUTO_EVOLVE_CADENCE` env var, or
#   2. a `cadence_minutes` integer in rabbit-auto-evolve's OWN state-dir config
#      file `<state_dir>/auto-evolve-cadence-config.json` (mirroring
#      log-tick.py's auto-evolve-log-config.json; NOT rabbit-cage/rabbit-config).
# Both scheduler paths DERIVE from the SAME resolved cadence at install time.
# ---------------------------------------------------------------------------
CADENCE_ENV = "RABBIT_AUTO_EVOLVE_CADENCE"
CADENCE_CONFIG_NAME = "auto-evolve-cadence-config.json"


def _state_dir():
    """Resolve rabbit-auto-evolve's state dir (matches log-tick.py / log-path.py:
    `RABBIT_AUTO_EVOLVE_STATE_DIR` wins, else `<cwd>/.rabbit`)."""
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _valid_cadence(value):
    """Coerce `value` to a sane sub-hour cadence int, or None if invalid.
    Valid = an integer (or integer-valued) in 1..59. Strings like '15' count;
    'abc', '', 0, 60, -5, 1.5 do NOT."""
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        return None
    if isinstance(value, int):
        n = value
    elif isinstance(value, str):
        try:
            n = int(value.strip())
        except (ValueError, AttributeError):
            return None
    else:
        return None
    if 1 <= n <= 59:
        return n
    return None


def _config_cadence_raw():
    """Return the raw `cadence_minutes` value from the state-dir config file,
    or None when the file is absent/unreadable/lacks the key."""
    path = os.path.join(_state_dir(), CADENCE_CONFIG_NAME)
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data.get("cadence_minutes")
    return None


def _configured_cadence(warnings=None):
    """Resolve the EFFECTIVE cadence (issue #722) with precedence
    env > config file > CADENCE_MINUTES default. Each source is VALIDATED via
    `_valid_cadence`; an invalid source is SKIPPED (the next source wins) and,
    when `warnings` is a list, a human-readable note about the ignored value is
    appended so install() can surface a branded warning. When no source yields
    a valid value the default `CADENCE_MINUTES` is returned."""
    env_raw = os.environ.get(CADENCE_ENV)
    if env_raw is not None and env_raw != "":
        valid = _valid_cadence(env_raw)
        if valid is not None:
            return valid
        if warnings is not None:
            warnings.append(
                f"{CADENCE_ENV}={env_raw!r} is not an integer in 1..59 — "
                f"ignoring it")

    cfg_raw = _config_cadence_raw()
    if cfg_raw is not None:
        valid = _valid_cadence(cfg_raw)
        if valid is not None:
            return valid
        if warnings is not None:
            warnings.append(
                f"{CADENCE_CONFIG_NAME} cadence_minutes={cfg_raw!r} is not an "
                f"integer in 1..59 — ignoring it")

    return CADENCE_MINUTES
# The recurring heartbeat fires the INTERNAL `tick` (the scripted phase-walk
# that RESPECTS the stop marker at phase 0 and NEVER deletes it), NOT the
# USER-intent `start` whose Inv 19 stop-cancel would silently resurrect a
# user-halted loop on a MACHINE wake-up. (The crontab path already fires the
# headless `tick-headless.py`; this prompt is the croncreate-fallback's
# equivalent.)
HEARTBEAT_PROMPT = "/rabbit-auto-evolve tick"

# A restricted-crontab denial (issue #507) is recognised by this phrase in
# the binary's stderr — the standard message is "You (<user>) are not
# allowed to use this program (crontab)". The legitimate empty case ("no
# crontab for <user>") does NOT contain it.
_RESTRICTED_SIGNAL = "not allowed"


class CrontabRestricted(Exception):
    """Raised when the `crontab` binary refuses with a permission denial."""


def _crontab_cmd():
    return os.environ.get("RABBIT_CRONTAB_CMD", "crontab")


def _repo_root():
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT", os.getcwd())


def _import_rabbit_print():
    """Lazy-import rabbit_print from the contract feature's scripts dir
    (not on sys.path by default). Mirrors set-evolve-mode.py's pattern."""
    here = os.path.dirname(os.path.abspath(__file__))
    scripts_dir = os.path.normpath(
        os.path.join(here, "..", "..", "contract", "scripts"))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from rabbit_print import rabbit_print  # noqa: PLC0415
    return rabbit_print


def _is_restricted(stderr):
    return _RESTRICTED_SIGNAL in (stderr or "").lower()


def _entry_line(repo_root, cadence=CADENCE_MINUTES):
    """The system-cron entry line, with its schedule DERIVED from `cadence`
    (the resolved operational cadence, #722). Defaults to CADENCE_MINUTES so
    callers that don't tune cadence are unaffected."""
    schedule = _system_cron_expr(cadence)
    return (
        f"{schedule} cd {repo_root} && python3 {TICK_SCRIPT} "
        f">> {LOG_PATH} 2>&1"
    )


def _read_crontab():
    """Return the current crontab text, or '' when the user has no crontab.

    `crontab -l` exits non-zero (typically 1) with a "no crontab for <user>"
    message when no crontab exists — that is the legitimate empty case, NOT
    an error, so we treat any non-zero exit as an empty crontab.

    A non-zero exit whose stderr carries a permission denial ("not allowed")
    is instead a RESTRICTED host (issue #507); raise CrontabRestricted so
    install() can fall back gracefully.
    """
    proc = subprocess.run(
        [_crontab_cmd(), "-l"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        if _is_restricted(proc.stderr):
            raise CrontabRestricted()
        return ""
    return proc.stdout


def _write_crontab(text):
    """Replace the crontab with `text` via `crontab -`. Returns True on
    success. Raises CrontabRestricted when the write is refused with a
    permission denial (issue #507)."""
    proc = subprocess.run(
        [_crontab_cmd(), "-"],
        input=text, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        if _is_restricted(proc.stderr):
            raise CrontabRestricted()
        sys.stderr.write(
            f"install-cron: `crontab -` failed (exit {proc.returncode}): "
            f"{proc.stderr}\n"
        )
        return False
    return True


def _report_restricted(repo_root, cadence=CADENCE_MINUTES):
    """Emit the CronCreate-fallback signal and a branded notice, then return
    0 (graceful, non-fatal). See issues #507, #521 / spec Inv 32, 34.

    A script CANNOT call `CronCreate` (it is a Claude tool), so this emits:
      (a) a machine-readable JSON signal on stdout naming the durable
          heartbeat the DISPATCHER must create on the next `start`, and
      (b) a branded rabbit_print line for the human.

    The heartbeat cron is DERIVED from the SAME resolved `cadence` (#722) the
    system-cron path uses, so both paths move together."""
    signal = {
        "scheduler": "croncreate",
        "action": "dispatcher-must-create-heartbeat",
        "cron": _heartbeat_expr(cadence),
        "prompt": HEARTBEAT_PROMPT,
        "durable": True,
    }
    print(json.dumps(signal))

    rabbit_print = _import_rabbit_print()
    lines = [
        rabbit_print(
            "crontab is restricted on this host — falling back to a durable "
            "CronCreate heartbeat.", "⚠", "yellow"),
        rabbit_print(
            "The durable CronCreate heartbeat will be set up on your next "
            "`/rabbit-auto-evolve start`.", "→", "yellow"),
    ]
    print("\n".join(lines))
    return 0


def _warn_rejected_cadence(warnings):
    """Surface a branded warning for each ignored/invalid cadence source
    (#722). Best-effort: a rabbit_print import failure must not break install."""
    if not warnings:
        return
    try:
        rabbit_print = _import_rabbit_print()
    except Exception:  # noqa: BLE001 — branding is non-essential
        for w in warnings:
            sys.stderr.write(f"install-cron: invalid cadence config — {w}; "
                             f"using the default cadence\n")
        return
    for w in warnings:
        print(rabbit_print(
            f"invalid cadence config — {w}; using the default "
            f"{CADENCE_MINUTES}-minute cadence.", "⚠", "yellow"))


def install():
    repo_root = _repo_root()
    # Resolve the operational cadence ONCE; BOTH scheduler paths derive from it.
    warnings = []
    cadence = _configured_cadence(warnings)
    _warn_rejected_cadence(warnings)

    try:
        current = _read_crontab()
    except CrontabRestricted:
        return _report_restricted(repo_root, cadence)

    # Idempotency: an entry mentioning tick-headless.py already present is a
    # clean no-op.
    if ENTRY_TOKEN in current:
        print("install-cron: tick-headless entry already present — no-op")
        return 0

    entry = _entry_line(repo_root, cadence)
    # Preserve existing lines; append the new entry with a trailing newline.
    if current and not current.endswith("\n"):
        current += "\n"
    new_crontab = current + entry + "\n"

    try:
        wrote = _write_crontab(new_crontab)
    except CrontabRestricted:
        return _report_restricted(repo_root, cadence)
    if not wrote:
        return 1
    print(f"install-cron: installed tick-headless entry: {entry}")
    return 0


def main():
    argparse.ArgumentParser(
        description="Idempotently install the system-cron entry that fires "
                    "the rabbit-auto-evolve headless tick (Inv 32 / #414)."
    ).parse_args()
    return install()


if __name__ == "__main__":
    sys.exit(main())
