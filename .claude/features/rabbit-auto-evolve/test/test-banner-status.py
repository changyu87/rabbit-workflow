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


def _run(repo_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


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


print("test-banner-status.py")

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

# --- t4b (#793): active only, state file PRESENT → existing idle 'paste' line ---
# Loop has been started at least once; retain the unchanged idle/active line.
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE])
    _seed_state(td)
    r = _run(td)
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
        elif line2.get("color") != "yellow":
            fail_t("idle", f"line2 color != yellow: {line2!r}")
        else:
            ok("idle", "state-file-present → idle 'paste: /rabbit-auto-evolve start' line")

# --- t5: active + running → line2 contains 'loop in progress' ---
with tempfile.TemporaryDirectory() as td_str:
    td = Path(td_str)
    _seed(td, [ACTIVE, RUNNING])
    r = _run(td)
    data = _parse(r)
    if not data.get("active"):
        fail_t("running", f"active not true: {data!r}")
    elif "loop in progress" not in (data.get("line2") or {}).get("text", ""):
        fail_t("running", f"line2 missing 'loop in progress': {data.get('line2')!r}")
    elif (data.get("line2") or {}).get("color") != "yellow":
        fail_t("running", f"line2 color != yellow: {data.get('line2')!r}")
    else:
        ok("running", "line2 contains 'loop in progress'")

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
