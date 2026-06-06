#!/usr/bin/env python3
"""test-tick-jitter.py — spec Inv 56 (#881, third reopen).

`scripts/tick-jitter.py` owns the empirical CronCreate jitter offset. CronCreate
applies a DETERMINISTIC per-job jitter to recurring tasks (a recurring job fires
up to 10% of its period late, capped at 15 min). On an idle session this is a
stable constant — observed `+13` min for the `13,43 * * * *` (30-min period)
heartbeat. This is NOT a range and NOT idle-gating.

The helper computes the offset as the median of
`actual_fire_time − nearest_prior_cron_boundary` over the recent fires recorded
in `.rabbit/tick.log` (Inv 36; each JSON line carries an ISO-8601 UTC `ts`), and
persists it to the rabbit-auto-evolve-owned state artifact
`.rabbit/auto-evolve-tick-jitter.json` so other features can READ it without
importing this feature. With NO recorded fire history it falls back to the
documented cold-start bound `min(15, ceil(period_minutes * 0.10))` and marks
`cold_start: true`.

State-dir resolution honors RABBIT_AUTO_EVOLVE_STATE_DIR (matching tick-log.py /
update-state.py). The cadence source is the repo-root
`.claude/scheduled_tasks.json` (the tasks[] entry whose prompt references
rabbit-auto-evolve), resolved via RABBIT_AUTO_EVOLVE_REPO_ROOT.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "tick-jitter.py"
ARTIFACT_NAME = "auto-evolve-tick-jitter.json"
TICK_LOG = "tick.log"

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


def _seed_cadence(repo_root: Path, cron: str) -> None:
    claude_dir = repo_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    payload = {"tasks": [{"id": "hb", "cron": cron,
                          "prompt": "/rabbit-auto-evolve tick"}]}
    (claude_dir / "scheduled_tasks.json").write_text(json.dumps(payload))


def _seed_tick_log(state_dir: Path, fire_ts: list[str]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for ts in fire_ts:
        lines.append(json.dumps({"ts": ts, "decision": "entering", "detail": ""}))
    (state_dir / TICK_LOG).write_text("\n".join(lines) + "\n")


def _run(subcmd: str, repo_root: Path, state_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = str(state_dir)
    return subprocess.run(
        [sys.executable, str(SCRIPT), subcmd],
        env=env, capture_output=True, text=True,
    )


print("test-tick-jitter.py")

# --- t1: script exists ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# --- t2: --help smoke test ---
r = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                   capture_output=True, text=True)
if r.returncode != 0:
    fail_t("help", f"--help exit {r.returncode}; stderr={r.stderr!r}")
elif "usage" not in r.stdout.lower():
    fail_t("help", f"--help lacks usage: {r.stdout!r}")
else:
    ok("help", "--help exits 0 with usage text")

# --- t3 (#881 CORE): a +13 fire history yields observed_jitter_minutes == 13 ---
# Cron 13,43 * * * *; the loop fired at :56 and :26 (constant +13 from the :43
# and :13 boundaries). The median offset MUST be exactly 13 — NOT the naive
# min(15, ceil(30*0.10)) == 3 which contradicts the observed evidence.
with tempfile.TemporaryDirectory() as root_str, tempfile.TemporaryDirectory() as st_str:
    root = Path(root_str)
    st = Path(st_str)
    _seed_cadence(root, "13,43 * * * *")
    _seed_tick_log(st, [
        "2026-06-04T21:56:04Z",
        "2026-06-04T22:26:11Z",
        "2026-06-04T22:56:02Z",
    ])
    r = _run("show", root, st)
    if r.returncode != 0:
        fail_t("observed-13", f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            data = json.loads(r.stdout)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            fail_t("observed-13", f"non-JSON stdout: {r.stdout!r}")
        elif data.get("observed_jitter_minutes") != 13:
            fail_t("observed-13",
                   f"observed_jitter_minutes != 13: {data!r}")
        elif data.get("cold_start") is not False:
            fail_t("observed-13", f"cold_start must be False with history: {data!r}")
        elif data.get("observed_jitter_minutes") == 3:
            fail_t("observed-13", "naive +3 formula MUST NOT win over observed +13")
        else:
            ok("observed-13", "median offset over +13 fire history == 13 (not naive +3)")

# --- t4: cold-start fallback when there is NO fire history ---
# No tick.log => fall back to min(15, ceil(period*0.10)). For a 30-min period
# that is min(15, ceil(3.0)) == 3, and cold_start must be True.
with tempfile.TemporaryDirectory() as root_str, tempfile.TemporaryDirectory() as st_str:
    root = Path(root_str)
    st = Path(st_str)
    _seed_cadence(root, "13,43 * * * *")  # period 30
    r = _run("show", root, st)
    expected_cold = min(15, math.ceil(30 * 0.10))
    try:
        data = json.loads(r.stdout)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        fail_t("cold-start", f"non-JSON stdout: {r.stdout!r}")
    elif data.get("cold_start") is not True:
        fail_t("cold-start", f"cold_start must be True with no history: {data!r}")
    elif data.get("observed_jitter_minutes") != expected_cold:
        fail_t("cold-start",
               f"cold fallback != {expected_cold}: {data!r}")
    else:
        ok("cold-start",
           f"no history => cold fallback min(15, ceil(30*0.10))=={expected_cold}, cold_start True")

# --- t5: cold-start cap at 15 for a long period ---
# Cron "0 * * * *" => period 60; ceil(60*0.10)=6, min(15,6)=6.
with tempfile.TemporaryDirectory() as root_str, tempfile.TemporaryDirectory() as st_str:
    root = Path(root_str)
    st = Path(st_str)
    _seed_cadence(root, "0 * * * *")  # period 60
    r = _run("show", root, st)
    data = json.loads(r.stdout)
    if data.get("observed_jitter_minutes") != 6:
        fail_t("cold-period-60", f"period-60 cold fallback != 6: {data!r}")
    else:
        ok("cold-period-60", "period-60 cold fallback == 6")

# --- t6: compute persists the artifact with the full schema ---
with tempfile.TemporaryDirectory() as root_str, tempfile.TemporaryDirectory() as st_str:
    root = Path(root_str)
    st = Path(st_str)
    _seed_cadence(root, "13,43 * * * *")
    _seed_tick_log(st, [
        "2026-06-04T21:56:04Z",
        "2026-06-04T22:26:11Z",
    ])
    r = _run("compute", root, st)
    artifact = st / ARTIFACT_NAME
    if r.returncode != 0:
        fail_t("persist", f"compute exit {r.returncode}; stderr={r.stderr!r}")
    elif not artifact.is_file():
        fail_t("persist", f"artifact not written: {artifact}")
    else:
        data = json.loads(artifact.read_text())
        required = {"schema_version", "observed_jitter_minutes", "period_minutes",
                    "sample_count", "cold_start", "computed_at", "owner",
                    "deprecation_criterion"}
        missing = required - set(data)
        if missing:
            fail_t("persist", f"artifact missing keys {missing}: {data!r}")
        elif data.get("observed_jitter_minutes") != 13:
            fail_t("persist", f"persisted offset != 13: {data!r}")
        elif data.get("sample_count") != 2:
            fail_t("persist", f"sample_count != 2: {data!r}")
        elif data.get("period_minutes") != 30:
            fail_t("persist", f"period_minutes != 30: {data!r}")
        elif data.get("owner") != "rabbit-workflow team":
            fail_t("persist", f"owner not rabbit-workflow team: {data!r}")
        else:
            ok("persist", "compute persists full-schema artifact (offset 13, samples 2)")

# --- t7: median (not mean) is used — an outlier fire does not skew the value ---
# Boundaries 13,43; fires at +13, +13, +13, and one outlier +1 (a mid-query
# late boundary delivered immediately). Median of [1,13,13,13] == 13.
with tempfile.TemporaryDirectory() as root_str, tempfile.TemporaryDirectory() as st_str:
    root = Path(root_str)
    st = Path(st_str)
    _seed_cadence(root, "13,43 * * * *")
    _seed_tick_log(st, [
        "2026-06-04T20:14:00Z",  # boundary 20:13 -> +1 (outlier)
        "2026-06-04T20:56:00Z",  # boundary 20:43 -> +13
        "2026-06-04T21:26:00Z",  # boundary 21:13 -> +13
        "2026-06-04T21:56:00Z",  # boundary 21:43 -> +13
    ])
    r = _run("show", root, st)
    data = json.loads(r.stdout)
    if data.get("observed_jitter_minutes") != 13:
        fail_t("median", f"median over outlier history != 13: {data!r}")
    else:
        ok("median", "median offset robust to a single outlier fire == 13")

# --- t8: unreadable/absent cadence => graceful (no crash, exit 0) ---
with tempfile.TemporaryDirectory() as root_str, tempfile.TemporaryDirectory() as st_str:
    root = Path(root_str)  # no scheduled_tasks.json seeded
    st = Path(st_str)
    r = _run("show", root, st)
    if r.returncode != 0:
        fail_t("no-cadence", f"must not crash on absent cadence; exit {r.returncode}, stderr={r.stderr!r}")
    else:
        ok("no-cadence", "absent cadence degrades gracefully (exit 0)")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
