#!/usr/bin/env python3
"""test-banner-status.py — spec Inv 22 (added v0.7.5 for issue #380).

`scripts/banner-status.py` owns the active-banner line-2 text variants.
Inspects rabbit-auto-evolve's runtime markers at the repo root and emits a
JSON object on stdout describing the active banner. Always exits 0.

When `.rabbit-auto-evolve-active` is absent:
  {"active": false, "line1": null, "line2": null}

When `.rabbit-auto-evolve-active` is present:
  {
    "active": true,
    "line1": {"text": "AUTONOMOUS-EVOLVE MODE ACTIVE", "icon": "...", "color": "red"},
    "line2": {"text": "<per precedence>", "icon": "...", "color": "..."}
  }

Line-2 precedence (first match wins):
  aborted (highest)  → "loop aborted on safety violation"   icon, red
  restart-needed     → "resume after restart"               icon, yellow
  running (NEW)      → "loop in progress"                   icon, yellow
  none, state ABSENT → "auto-evolve configured — restart … start"  ⏸, yellow (#793)
  none, state PRESENT→ "paste: /rabbit-auto-evolve start"   ▶,  yellow

The two `none` sub-cases (#793) distinguish the post-`on`/pre-`start` window
(`.rabbit/auto-evolve-state.json` absent — only start-loop.py creates it) from
a started-then-idle loop (state file present). The restart-pending line2 is
emitted VERBATIM the same as `contract.lib.runtime.emit_auto_evolve_stop_line`
so the SessionStart banner and the Stop line agree.

The script honors RABBIT_AUTO_EVOLVE_REPO_ROOT for test isolation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "banner-status.py"

ACTIVE = ".rabbit-auto-evolve-active"
RUNNING = ".rabbit-auto-evolve-running"
RESTART = ".rabbit-auto-evolve-restart-needed"
ABORTED = ".rabbit-auto-evolve-aborted"

# #793: the never-started signal — absence of this file means the loop was
# configured by `on` but never started (only start-loop.py creates it).
STATE_FILE = ".rabbit/auto-evolve-state.json"

# #793: the restart-pending line2, VERBATIM the same as the Stop line in
# contract.lib.runtime so SessionStart and Stop agree.
RESTART_PENDING_TEXT = (
    "auto-evolve configured — restart Claude Code, then run "
    "/rabbit-auto-evolve start"
)


pass_n = 0
fail_n = 0


def ok(t: str, msg: str) -> None:
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t: str, msg: str) -> None:
    global fail_n
    print(f"  FAIL {t}: {msg}")
    fail_n += 1


def _run(repo_root: Path, now: str | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    # #844: inject a fixed wall-clock so the idle next-tick ETA is deterministic
    # (never the real clock). Absent => script falls back to the real clock.
    if now is not None:
        env["RABBIT_AUTO_EVOLVE_NOW"] = now
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


def _seed_cadence(td: Path, cron: str, prompt: str = "/rabbit-auto-evolve tick") -> None:
    """#844: write the heartbeat cadence source the idle ETA reads — the
    repo-root .claude/scheduled_tasks.json entry whose prompt references
    rabbit-auto-evolve (mirrors contract Inv 55's cadence source)."""
    claude_dir = td / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    payload = {"tasks": [{"id": "hb", "cron": cron, "prompt": prompt}]}
    (claude_dir / "scheduled_tasks.json").write_text(json.dumps(payload))


def _seed_jitter(td: Path, observed: int, cold_start: bool = False) -> None:
    """#881 (Inv 56): write the rabbit-auto-evolve-owned jitter offset the idle
    ETA adds to the next cron boundary. The banner renders boundary + observed
    as a single EXACT HH:MM (no >=, no ~, no qualifier)."""
    state_dir = td / ".rabbit"
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "observed_jitter_minutes": observed,
        "period_minutes": 30,
        "sample_count": 3,
        "cold_start": cold_start,
        "computed_at": "2026-06-04T22:56:00Z",
        "owner": "rabbit-workflow team",
        "deprecation_criterion": "n/a",
    }
    (state_dir / "auto-evolve-tick-jitter.json").write_text(json.dumps(payload))


def _seed(td: Path, names: list[str], content: str = "session") -> None:
    for n in names:
        (td / n).write_text(content)


def _seed_state(td: Path) -> None:
    """Create .rabbit/auto-evolve-state.json — the loop-started signal (#793)."""
    state_path = td / STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{}")


def _parse(r: subprocess.CompletedProcess) -> dict:
    return json.loads(r.stdout)


def _import_banner_module():
    """Import scripts/banner-status.py as a module for direct unit coverage."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("banner_status_mod", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("test-banner-status.py")

# --- t0 (#881 third reopen): the rejected mental-model helpers are GONE ---
# Two prior cycles were REJECTED: (1) the #883 "(scheduler jitter)" range and
# (2) the idle-gating "≥ HH:MM (fires when the session is next idle)" lower
# bound. The ACCEPTED root cause is CronCreate's DETERMINISTIC per-job jitter:
# recurring tasks fire up to 10% of their period late (capped 15 min); on an
# idle session this is a stable constant (observed +13 for 13,43). The display
# is now the EXACT boundary + observed offset. The old jitter-range helpers
# MUST be gone.
_mod = _import_banner_module()
if hasattr(_mod, "_cadence_jitter_minutes") or hasattr(_mod, "_cadence_period_minutes"):
    fail_t("no-jitter-helpers", "old jitter-range helpers must be removed (#881)")
else:
    ok("no-jitter-helpers", "old jitter-range helpers removed")

# --- t0b (#881 cleanup pass): NONE of the rejected wording remains in source ---
# The maintainer-directed purge: no "(scheduler jitter)" range, no idle-gating,
# no "≥" lower-bound framing, no "(fires when the session is next idle)".
_SRC = SCRIPT.read_text(encoding="utf-8")
_FORBIDDEN = [
    "fires when the session is next idle",
    "scheduler jitter",
    "≥",
    "idle-gat",
    "cron jitter",
    "next goes idle",
    "LOWER bound",
    "lower-bound",
]
_hits = [p for p in _FORBIDDEN if p in _SRC]
if _hits:
    fail_t("purged-wording", f"banner-status.py still contains rejected wording: {_hits!r}")
else:
    ok("purged-wording", "no rejected mental-model wording remains in banner-status.py")

# --- t1: script exists on disk ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# --- t2: --help smoke test ---
r = subprocess.run(
    [sys.executable, str(SCRIPT), "--help"],
    capture_output=True,
    text=True,
)
if r.returncode != 0:
    fail_t("help", f"--help exit {r.returncode}; stderr={r.stderr!r}")
elif "usage" not in r.stdout.lower():
    fail_t("help", f"--help output lacks usage text: {r.stdout!r}")
else:
    ok("help", "--help exits 0 with usage text")

# --- t3: active marker absent → active: false ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    r = _run(td)
    if r.returncode != 0:
        fail_t("absent", f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        data = _parse(r)
        if data == {"active": False, "line1": None, "line2": None}:
            ok("absent", "active=false, line1/line2=null")
        else:
            fail_t("absent", f"unexpected payload: {data!r}")

# --- t4a (#793): active only, state file ABSENT → restart-pending line2 ---
# Post-`on`/pre-`start` window: configured but never started. Must emit the
# restart-pending line2 VERBATIM the same as the symmetric Stop line.
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    r = _run(td)
    if r.returncode != 0:
        fail_t("restart-pending", f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        data = _parse(r)
        line2 = data.get("line2") or {}
        if not data.get("active"):
            fail_t("restart-pending", f"active not true: {data!r}")
        elif "AUTONOMOUS-EVOLVE MODE ACTIVE" not in (data.get("line1") or {}).get("text", ""):
            fail_t("restart-pending", f"line1 missing expected text: {data.get('line1')!r}")
        elif line2.get("text") != RESTART_PENDING_TEXT:
            fail_t("restart-pending", f"line2.text != restart-pending exact wording: {line2!r}")
        elif line2.get("icon") != "⏸":
            fail_t("restart-pending", f"line2.icon != ⏸: {line2!r}")
        elif line2.get("color") != "yellow":
            fail_t("restart-pending", f"line2 color != yellow: {line2!r}")
        else:
            ok("restart-pending", "state-file-absent → exact restart-pending line2 (⏸, yellow)")

# --- t4b (#793): active only, state file PRESENT, NO cadence source →
# bare idle 'paste' line, NO ETA (graceful fallback, #844). ---
# Loop has been started at least once; retain the unchanged idle/active line.
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    _seed_state(td)
    r = _run(td, now="2026-06-04T14:05:00")  # cadence source deliberately absent
    if r.returncode != 0:
        fail_t("idle", f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        data = _parse(r)
        line2 = data.get("line2") or {}
        if not data.get("active"):
            fail_t("idle", f"active not true: {data!r}")
        elif "paste: /rabbit-auto-evolve start" not in line2.get("text", ""):
            fail_t("idle", f"line2 missing 'paste: ...': {line2!r}")
        elif line2.get("text") == RESTART_PENDING_TEXT:
            fail_t("idle", f"line2 must NOT be restart-pending when state present: {line2!r}")
        elif "next tick" in line2.get("text", ""):
            fail_t("idle", f"line2 must NOT carry ETA when cadence absent: {line2!r}")
        elif line2.get("color") != "yellow":
            fail_t("idle", f"line2 color != yellow: {line2!r}")
        else:
            ok("idle", "state-file-present, no cadence → bare idle line, no ETA")

# --- t4c (#881 third reopen): the idle line carries the EXACT next-tick time —
# the next cron boundary PLUS the observed CronCreate jitter offset (Inv 56),
# rendered as a single bare HH:MM. NO ">=", NO "~", NO range, NO qualifier.
# For a 13,43 cadence from now=14:20 the next boundary is 14:43; with a +13
# observed offset the displayed time is 14:56 ("next tick 14:56"). ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    _seed_state(td)
    _seed_cadence(td, "13,43 * * * *")
    _seed_jitter(td, 13)
    r = _run(td, now="2026-06-04T14:20:00")
    if r.returncode != 0:
        fail_t("idle-eta", f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        data = _parse(r)
        line2 = data.get("line2") or {}
        text = line2.get("text", "")
        if "paste: /rabbit-auto-evolve start" not in text:
            fail_t("idle-eta", f"line2 missing base idle text: {line2!r}")
        elif ", next tick 14:56" not in text:
            fail_t("idle-eta", f"line2 missing exact boundary+offset ETA 14:56: {line2!r}")
        elif "≥" in text or "~" in text or "jitter" in text or "next idle" in text:
            fail_t("idle-eta", f"line2 must carry NO qualifier/range/jitter: {line2!r}")
        elif not re.search(r", next tick \d\d:\d\d$", text):
            fail_t("idle-eta", f"line2 ETA not a bare HH:MM at end: {line2!r}")
        elif line2.get("color") != "yellow":
            fail_t("idle-eta", f"line2 color != yellow: {line2!r}")
        else:
            ok("idle-eta", "idle line appends exact 'next tick 14:56' (boundary 14:43 + offset 13)")

# --- t4c2 (#881): a once-per-hour cadence (single fire minute). Cron
# "10 * * * *" from now=14:20 => next boundary 15:10; with a +6 offset the
# exact displayed time is 15:16 — a single bare HH:MM, no qualifier. ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    _seed_state(td)
    _seed_cadence(td, "10 * * * *")
    _seed_jitter(td, 6)
    r = _run(td, now="2026-06-04T14:20:00")
    text = (_parse(r).get("line2") or {}).get("text", "")
    if ", next tick 15:16" not in text:
        fail_t("idle-eta-hourly", f"once-per-hour boundary+offset ETA wrong: {text!r}")
    elif "≥" in text or "jitter" in text or "next idle" in text:
        fail_t("idle-eta-hourly", f"must carry no qualifier/jitter: {text!r}")
    else:
        ok("idle-eta-hourly", "once-per-hour cadence => exact 15:16 (boundary 15:10 + offset 6)")

# --- t4c3 (#881): offset wraps the hour. Boundary 14:43 + 20 offset => 15:03.
# Confirms the rendered minute carries the hour-carry correctly. ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    _seed_state(td)
    _seed_cadence(td, "13,43 * * * *")
    _seed_jitter(td, 20)
    r = _run(td, now="2026-06-04T14:20:00")
    text = (_parse(r).get("line2") or {}).get("text", "")
    if ", next tick 15:03" not in text:
        fail_t("idle-eta-wrap", f"offset hour-carry wrong (expected 15:03): {text!r}")
    else:
        ok("idle-eta-wrap", "boundary 14:43 + offset 20 => 15:03 (hour carry)")

# --- t4c4 (#881): cold-start — no jitter artifact present. The banner falls
# back to the documented cold bound min(15, ceil(period*0.10)); for a 30-min
# period that is +3, so boundary 14:43 + 3 => 14:46 as a bare HH:MM. ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    _seed_state(td)
    _seed_cadence(td, "13,43 * * * *")  # NO jitter artifact => cold start
    r = _run(td, now="2026-06-04T14:20:00")
    text = (_parse(r).get("line2") or {}).get("text", "")
    if ", next tick 14:46" not in text:
        fail_t("idle-eta-coldstart", f"cold-start fallback ETA wrong (expected 14:46): {text!r}")
    elif "≥" in text or "next idle" in text:
        fail_t("idle-eta-coldstart", f"cold-start must carry no qualifier: {text!r}")
    else:
        ok("idle-eta-coldstart", "no jitter artifact => cold fallback +3 => 14:46")

# --- t4d (#844): idle ETA degrades to bare line on an unparseable cadence ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    _seed_state(td)
    _seed_cadence(td, "not a cron")
    r = _run(td, now="2026-06-04T14:20:00")
    data = _parse(r)
    line2 = data.get("line2") or {}
    text = line2.get("text", "")
    if "paste: /rabbit-auto-evolve start" not in text:
        fail_t("idle-eta-fallback", f"line2 missing base idle text: {line2!r}")
    elif "next tick" in text:
        fail_t("idle-eta-fallback", f"line2 must NOT carry ETA on bad cron: {line2!r}")
    else:
        ok("idle-eta-fallback", "unparseable cron → bare idle line, no ETA")

# --- t4e (#844): the ETA only attaches to the idle line — the restart-pending
# (never-started) line carries NO ETA even when a cadence source is present. ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])  # state file deliberately absent => never-started
    _seed_cadence(td, "13,43 * * * *")
    r = _run(td, now="2026-06-04T14:20:00")
    data = _parse(r)
    line2 = data.get("line2") or {}
    if line2.get("text") != RESTART_PENDING_TEXT:
        fail_t("restart-pending-no-eta", f"expected exact restart-pending line: {line2!r}")
    elif "next tick" in line2.get("text", ""):
        fail_t("restart-pending-no-eta", f"restart-pending must NOT carry ETA: {line2!r}")
    else:
        ok("restart-pending-no-eta", "restart-pending line carries no ETA (cadence present)")

# --- t5: active + running → line2 contains 'loop in progress' ---
# Cadence + state present: a priority marker line must NOT carry an ETA (#844).
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, RUNNING])
    _seed_state(td)
    _seed_cadence(td, "13,43 * * * *")
    r = _run(td, now="2026-06-04T14:20:00")
    data = _parse(r)
    if not data.get("active"):
        fail_t("running", f"active not true: {data!r}")
    elif "loop in progress" not in (data.get("line2") or {}).get("text", ""):
        fail_t("running", f"line2 missing 'loop in progress': {data.get('line2')!r}")
    elif "next tick" in (data.get("line2") or {}).get("text", ""):
        fail_t("running", f"running line must NOT carry ETA: {data.get('line2')!r}")
    elif (data.get("line2") or {}).get("color") != "yellow":
        fail_t("running", f"line2 color != yellow: {data.get('line2')!r}")
    else:
        ok("running", "line2 contains 'loop in progress', no ETA")

# --- t6: active + restart-needed → line2 contains 'resume after restart' ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, RESTART])
    r = _run(td)
    data = _parse(r)
    if not data.get("active"):
        fail_t("restart", f"active not true: {data!r}")
    elif "resume after restart" not in (data.get("line2") or {}).get("text", ""):
        fail_t("restart", f"line2 missing 'resume after restart': {data.get('line2')!r}")
    elif (data.get("line2") or {}).get("color") != "yellow":
        fail_t("restart", f"line2 color != yellow: {data.get('line2')!r}")
    else:
        ok("restart", "line2 contains 'resume after restart'")

# --- t7: active + aborted → line2 contains 'loop aborted on safety violation' ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, ABORTED])
    r = _run(td)
    data = _parse(r)
    if not data.get("active"):
        fail_t("aborted", f"active not true: {data!r}")
    elif "loop aborted on safety violation" not in (data.get("line2") or {}).get("text", ""):
        fail_t("aborted", f"line2 missing 'loop aborted on safety violation': {data.get('line2')!r}")
    elif (data.get("line2") or {}).get("color") != "red":
        fail_t("aborted", f"line2 color != red: {data.get('line2')!r}")
    else:
        ok("aborted", "line2 contains 'loop aborted on safety violation'")

# --- t8: precedence active + running + restart-needed → restart-needed wins ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, RUNNING, RESTART])
    r = _run(td)
    data = _parse(r)
    text = (data.get("line2") or {}).get("text", "")
    if "resume after restart" not in text:
        fail_t("prec-restart>running", f"line2 should mention restart, got: {text!r}")
    elif "loop in progress" in text:
        fail_t("prec-restart>running", f"line2 should NOT mention 'loop in progress', got: {text!r}")
    else:
        ok("prec-restart>running", "restart-needed wins over running")

# --- t9: precedence active + running + aborted → aborted wins ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, RUNNING, ABORTED])
    r = _run(td)
    data = _parse(r)
    text = (data.get("line2") or {}).get("text", "")
    if "loop aborted on safety violation" not in text:
        fail_t("prec-aborted>running", f"line2 should mention aborted, got: {text!r}")
    elif "loop in progress" in text:
        fail_t("prec-aborted>running", f"line2 should NOT mention running, got: {text!r}")
    else:
        ok("prec-aborted>running", "aborted wins over running")

# --- t10: precedence active + restart-needed + aborted → aborted wins ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, RESTART, ABORTED])
    r = _run(td)
    data = _parse(r)
    text = (data.get("line2") or {}).get("text", "")
    if "loop aborted on safety violation" not in text:
        fail_t("prec-aborted>restart", f"line2 should mention aborted, got: {text!r}")
    elif "resume after restart" in text:
        fail_t("prec-aborted>restart", f"line2 should NOT mention restart, got: {text!r}")
    else:
        ok("prec-aborted>restart", "aborted wins over restart-needed")

# --- t12 (#793): a priority marker wins even when the state file is absent ---
# The never-started distinction only applies to the lowest-priority `none`
# branch; the four priority markers must still pre-empt restart-pending.
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, RUNNING])  # state file deliberately absent
    r = _run(td)
    data = _parse(r)
    line2 = data.get("line2") or {}
    if "loop in progress" not in line2.get("text", ""):
        fail_t("prec-running>restart-pending", f"running should win, got: {line2!r}")
    elif line2.get("text") == RESTART_PENDING_TEXT:
        fail_t("prec-running>restart-pending", f"must NOT be restart-pending: {line2!r}")
    else:
        ok("prec-running>restart-pending", "running marker wins over restart-pending (state absent)")

# --- t11: exit code is always 0 ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    # All four markers
    _seed(td, [ACTIVE, RUNNING, RESTART, ABORTED])
    r = _run(td)
    if r.returncode != 0:
        fail_t("exit-0", f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        ok("exit-0", "exit 0 even with all markers present")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
