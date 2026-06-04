#!/usr/bin/env python3
"""test-cron-cadence-source.py — single source of truth for the tick cadence
(issue #723).

Before #723 the cadence lived as TWO independent hardcoded literals in
install-cron.py: `SCHEDULE = "*/30 * * * *"` (system-cron path) and
`HEARTBEAT_EXPR = "13,43 * * * *"` (CronCreate fallback). They were decoupled —
changing the system-cron cadence left the fallback silently at the old value —
and the heartbeat literal was duplicated verbatim into docs/spec.md and the
source SKILL.md.

This e2e regression pins the fix:

  1. There is ONE codified cadence source (`CADENCE_MINUTES`) in
     install-cron.py from which BOTH paths derive.
  2. The fallback `HEARTBEAT_EXPR` is DERIVED (via `_heartbeat_expr`) from the
     SAME `CADENCE_MINUTES` as the system-cron `SCHEDULE` — it is NOT a second
     independent string literal. Changing the source value changes BOTH.
  3. The derived heartbeat avoids the :00 and :30 minute marks (CronCreate
     guidance) at the default 30-min cadence and remains so for other cadences.
  4. The doc/SKILL literals match the codified source (drift fails the gate).
"""

import importlib.util
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
INSTALL_CRON = FEATURE_DIR / "scripts" / "install-cron.py"
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load_install_cron():
    spec = importlib.util.spec_from_file_location("install_cron", INSTALL_CRON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = load_install_cron()

# --- (1) One codified cadence source ------------------------------------
if not hasattr(mod, "CADENCE_MINUTES"):
    fail("install-cron.py exposes no CADENCE_MINUTES source-of-truth constant")
    sys.exit(FAIL)
ok("install-cron.py exposes a single CADENCE_MINUTES cadence source")

if not isinstance(mod.CADENCE_MINUTES, int) or mod.CADENCE_MINUTES <= 0 \
        or mod.CADENCE_MINUTES >= 60:
    fail(f"CADENCE_MINUTES must be a 1..59 int; got {mod.CADENCE_MINUTES!r}")
else:
    ok(f"CADENCE_MINUTES is a sane sub-hour cadence ({mod.CADENCE_MINUTES})")

# Derivation helpers must exist so both paths COMPUTE rather than hardcode.
for fn in ("_system_cron_expr", "_heartbeat_expr"):
    if not hasattr(mod, fn) or not callable(getattr(mod, fn)):
        fail(f"install-cron.py missing derivation helper {fn}()")
if FAIL:
    sys.exit(FAIL)
ok("install-cron.py provides _system_cron_expr() and _heartbeat_expr() helpers")

# --- (2) Both paths derive from the SAME source -------------------------
# SCHEDULE must equal the system-cron derivation of CADENCE_MINUTES.
expected_schedule = mod._system_cron_expr(mod.CADENCE_MINUTES)
if mod.SCHEDULE != expected_schedule:
    fail(f"SCHEDULE {mod.SCHEDULE!r} != derivation of CADENCE_MINUTES "
         f"{expected_schedule!r} — system-cron path is not single-sourced")
else:
    ok("SCHEDULE derives from CADENCE_MINUTES")

# HEARTBEAT_EXPR must equal the heartbeat derivation of the SAME source.
expected_heartbeat = mod._heartbeat_expr(mod.CADENCE_MINUTES)
if mod.HEARTBEAT_EXPR != expected_heartbeat:
    fail(f"HEARTBEAT_EXPR {mod.HEARTBEAT_EXPR!r} != derivation of "
         f"CADENCE_MINUTES {expected_heartbeat!r} — fallback is not "
         f"single-sourced")
else:
    ok("HEARTBEAT_EXPR derives from the SAME CADENCE_MINUTES source")

# --- (2b) No second independent literal ---------------------------------
# The heartbeat must NOT be hardcoded: the source must not contain the raw
# heartbeat string as an assignment-RHS literal. We assert HEARTBEAT_EXPR is
# produced by the helper (already checked above) AND that flipping the source
# value to a DIFFERENT cadence flips BOTH derived expressions — proving they
# are coupled, not coincidentally equal.
src_text = INSTALL_CRON.read_text()
# A bare `HEARTBEAT_EXPR = "13,43 * * * *"` style literal is the regression.
if re.search(r'HEARTBEAT_EXPR\s*=\s*["\']\s*\d', src_text):
    fail("HEARTBEAT_EXPR is assigned a hardcoded string literal (regression: "
         "a second independent cadence source)")
else:
    ok("HEARTBEAT_EXPR is not a hardcoded string literal")
if re.search(r'SCHEDULE\s*=\s*["\']\s*\*?/?\d', src_text):
    fail("SCHEDULE is assigned a hardcoded string literal (regression: "
         "a second independent cadence source)")
else:
    ok("SCHEDULE is not a hardcoded string literal")

# Coupling proof: a different cadence must change BOTH derivations together.
alt = 15 if mod.CADENCE_MINUTES != 15 else 20
alt_sched = mod._system_cron_expr(alt)
alt_heart = mod._heartbeat_expr(alt)
if alt_sched != mod.SCHEDULE and alt_heart != mod.HEARTBEAT_EXPR:
    ok("changing the cadence source changes BOTH derived expressions")
else:
    fail(f"a different cadence ({alt}) did not change both expressions "
         f"(sched={alt_sched!r}, heart={alt_heart!r}) — paths are decoupled")

# --- (3) Derived heartbeat avoids :00 and :30 marks ---------------------
def avoids_marks(expr):
    minute_field = expr.split()[0]
    minutes = set()
    for part in minute_field.split(","):
        if "/" not in part and part.isdigit():
            minutes.add(int(part))
    # The heartbeat is an explicit comma-minute list; it must avoid 0 and 30.
    return 0 not in minutes and 30 not in minutes and bool(minutes)


if avoids_marks(mod.HEARTBEAT_EXPR):
    ok("default heartbeat avoids the :00 and :30 marks")
else:
    fail(f"default heartbeat {mod.HEARTBEAT_EXPR!r} hits a :00/:30 mark")
# Hold for a few other sub-hour cadences too (the derivation, not just 30).
for c in (10, 15, 20, 30):
    if not avoids_marks(mod._heartbeat_expr(c)):
        fail(f"heartbeat derivation for cadence {c} hits a :00/:30 mark: "
             f"{mod._heartbeat_expr(c)!r}")
        break
else:
    ok("heartbeat derivation avoids :00/:30 across several cadences")

# --- (4) Doc/SKILL literals match the codified source -------------------
# Wherever the spec.md or source SKILL.md states a concrete heartbeat cron
# literal, it MUST equal the codified HEARTBEAT_EXPR (drift fails the gate).
# Three literal shapes are pinned:
#   - the JSON signal field        `"cron":"<expr>"`
#   - the CronCreate call kwarg    `cron="<expr>"`
#   - a standalone backtick form   `` `<minute-list> * * * *` ``
HEARTBEAT_RES = [
    re.compile(r'"cron"\s*:\s*"([^"]+)"'),
    re.compile(r'\bcron\s*=\s*"([^"]+)"'),
    re.compile(r'`(\d+(?:,\d+)* \* \* \* \*)`'),
]
for path, label in ((SPEC_MD, "spec.md"), (SOURCE_SKILL, "source SKILL.md")):
    text = path.read_text()
    crons = []
    for rx in HEARTBEAT_RES:
        crons.extend(rx.findall(text))
    if not crons:
        ok(f"{label}: no hardcoded heartbeat cron literal (references source)")
        continue
    drifted = [c for c in crons if c != mod.HEARTBEAT_EXPR]
    if drifted:
        fail(f"{label}: heartbeat cron literal(s) {drifted!r} drifted from "
             f"the codified HEARTBEAT_EXPR {mod.HEARTBEAT_EXPR!r}")
    else:
        ok(f"{label}: every heartbeat cron literal matches the codified source")

# The system-cron schedule, where stated as a literal in prose, must also
# match the codified SCHEDULE. The fragile every-minute `*/1 * * * *` form is
# EXCLUDED: Inv 33 documents it on purpose as the explicitly-REJECTED form, so
# its presence is intentional and not a cadence-drift signal.
spec_text = SPEC_MD.read_text()
scheds = [s for s in re.findall(r'\*/\d+ \* \* \* \*', spec_text)
          if s != "*/1 * * * *"]
drifted = [s for s in scheds if s != mod.SCHEDULE]
if drifted:
    fail(f"spec.md: system-cron literal(s) {drifted!r} drifted from the "
         f"codified SCHEDULE {mod.SCHEDULE!r}")
elif scheds:
    ok("spec.md: every system-cron literal matches the codified SCHEDULE")

sys.exit(FAIL)
