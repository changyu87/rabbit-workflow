#!/usr/bin/env python3
"""test-spec-cron-invariant.py — rabbit-auto-evolve Inv 32 (issues #414,
#509, #521).

Inv 32 was AMENDED in place by #521 (+ #509's two-tier refinement): the
system cron is the scheduler WHERE AVAILABLE, and a durable `CronCreate`
heartbeat is the SANCTIONED fallback on crontab-restricted hosts.
`ScheduleWakeup` and `/loop` stay FORBIDDEN. This e2e regression asserts:

  1. The spec carries the amended Inv 32 text (system cron + the cross-refs
     #414/#509/#521).
  2. `ScheduleWakeup` and `/loop` are ABSENT from the spec.md and from BOTH
     SKILL.md copies.
  3. `CronCreate` is PRESENT in the SOURCE spec.md and the SOURCE
     feature-dir SKILL.md, described as the fallback (and explicitly NOT
     /loop). It is NOT asserted on the DEPLOYED copy — the deployed SKILL.md
     is out of this feature's scope and lags until redeployed under issue
     #511 (deferred deployed-copy parity).
  4. BOTH SKILL.md copies document the system cron and the headless tick
     (`tick-headless.py`).
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# Resolve the feature spec dual-read (issue #399): prefer the flat
# docs/spec.md layout, fall back to specs/spec.md, then legacy docs/spec/.
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
REPO_ROOT = FEATURE_DIR.parents[2]
DEPLOYED_SKILL = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) Spec carries the amended Inv 32 -------------------------------
spec = norm(SPEC_MD.read_text())
spec_low = spec.lower()

SPEC_REQUIRED = [
    "system cron",
    "tick-headless.py",
    "install-cron.py",
    "uninstall-cron.py",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing cron-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the amended cron-scheduling invariant (Inv 32)")

# --- (1b) Inv 33 pinned-minute one-shot amendment (#531) ----------------
# The croncreate one-shot must be a PINNED next-minute "M H * * *" expression
# (never the fragile "*/1 * * * *"), with recurring:false AND durable:false
# passed faithfully and at most one refire alive (CronList -> CronDelete ->
# CronCreate). The spec text MUST document this.
PINNED_REQUIRED = [
    "recurring: false",
    "durable: false",
    "pinned",
]
pin_missing = [s for s in PINNED_REQUIRED if s.lower() not in spec_low]
if pin_missing:
    fail(f"spec.md missing Inv 33 pinned-minute phrase(s): {pin_missing!r}")
else:
    ok("spec.md documents the Inv 33 pinned-minute one-shot amendment (#531)")
# Arm-time minute-boundary skid buffer (#748): the pinned minute must carry a
# >=2-minute buffer so the dispatcher's dedup round-trip cannot cross the
# minute boundary and park the one-shot ~24h out. The spec text MUST document
# this buffer rationale.
SKID_REQUIRED = ["minute + 2", "buffer"]
skid_missing = [s for s in SKID_REQUIRED if s.lower() not in spec_low]
if skid_missing:
    fail(f"spec.md missing Inv 33 arm-time-skid buffer phrase(s): {skid_missing!r}")
else:
    ok("spec.md documents the Inv 33 arm-time-skid minute buffer (#748)")
# The spec must explicitly reject the every-minute form.
if "*/1 * * * *" in spec and "never" in spec_low:
    ok("spec.md rejects the fragile every-minute '*/1 * * * *' form")
else:
    fail("spec.md does not reject the every-minute '*/1 * * * *' form")

# --- (2) ScheduleWakeup and /loop are FORBIDDEN -------------------------
# The amended Inv 32 names ScheduleWakeup/loop only to FORBID them, so the
# tokens DO appear in the spec as forbidden-list items. We therefore require
# the spec to keep its forbidden statement, and we assert TOTAL ABSENCE only
# in the SKILL.md copies (where the forbidden mechanisms must never be wired).
if "schedulewakeup" in spec_low and "forbidden" in spec_low:
    ok("spec.md keeps ScheduleWakeup/loop on the FORBIDDEN list")
else:
    fail("spec.md does not document ScheduleWakeup/loop as FORBIDDEN")

# --- (3) CronCreate is PRESENT in the SOURCE spec as the fallback -------
if "croncreate" in spec_low and "fallback" in spec_low:
    ok("spec.md documents CronCreate as the sanctioned fallback")
else:
    fail("spec.md does not document CronCreate as the fallback")
# Accept the clarifier with or without the markdown backtick around /loop.
# `spec_low` is whitespace-normalized so line-wrapped phrasing still matches.
if "not /loop" in spec_low or "not `/loop`" in spec_low:
    ok("spec.md clarifies CronCreate is NOT /loop")
else:
    fail("spec.md does not clarify CronCreate is NOT /loop")


# --- (2)+(4) SKILL.md copies -------------------------------------------
def check_skill_common(path, label):
    """Checks that apply to BOTH copies: ScheduleWakeup/loop absent; system
    cron + headless tick documented."""
    if not path.is_file():
        fail(f"{label} SKILL.md not found at {path}")
        return None
    body = path.read_text()
    flat = norm(body)
    flat_low = flat.lower()

    if "schedulewakeup" in flat_low:
        fail(f"{label}: SKILL.md still references ScheduleWakeup (forbidden)")
    else:
        ok(f"{label}: no ScheduleWakeup reference")

    if "/loop" in flat_low:
        fail(f"{label}: SKILL.md still references /loop (forbidden)")
    else:
        ok(f"{label}: no /loop reference")

    if "cron" in flat_low:
        ok(f"{label}: documents the system cron")
    else:
        fail(f"{label}: does not mention the system cron")

    if "tick-headless.py" in flat_low:
        ok(f"{label}: documents the headless tick (tick-headless.py)")
    else:
        fail(f"{label}: does not document tick-headless.py")
    return flat_low


# Source copy: ScheduleWakeup/loop absent + cron/headless documented, AND
# CronCreate PRESENT as the fallback (not /loop).
src_low = check_skill_common(SOURCE_SKILL, "source")
if src_low is not None:
    if "croncreate" in src_low and "fallback" in src_low:
        ok("source: SKILL.md documents CronCreate as the fallback trigger")
    else:
        fail("source: SKILL.md does not document CronCreate as the fallback")
    # The source SKILL keeps the forbidden tokens OUT entirely (they live in
    # spec Inv 32). It must describe CronCreate as NOT an in-session wakeup
    # harness without naming the forbidden mechanisms verbatim.
    if "idle-repl" in src_low or "not an in-session" in src_low:
        ok("source: SKILL.md frames CronCreate as a non-wakeup idle scheduler")
    else:
        fail("source: SKILL.md does not frame CronCreate vs the wakeup harness")

# Deployed copy: ONLY the ScheduleWakeup/loop-absence + cron/headless checks.
# CronCreate presence is DEFERRED to issue #511's deployment sync — the
# deployed SKILL.md is out of this feature's edit scope and will lag until
# redeployed; asserting CronCreate presence here would fail until then.
check_skill_common(DEPLOYED_SKILL, "deployed")

sys.exit(FAIL)
